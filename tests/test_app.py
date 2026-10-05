import sqlite3
import uuid
from contextlib import closing
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from stride import create_app


class AppTests(unittest.TestCase):
    def setUp(self):
        instance = Path(__file__).resolve().parents[1] / 'instance'
        instance.mkdir(exist_ok=True)
        self.path = str(instance / f'test-{uuid.uuid4().hex}.sqlite')
        self.app = create_app({'TESTING': True, 'SECRET_KEY': 'test-key', 'DATABASE': self.path})
        self.owner, self.member, self.outsider = (self.app.test_client() for _ in range(3))
        for client, name in [(self.owner, 'Owner'), (self.member, 'Member'), (self.outsider, 'Outsider')]:
            response = self.post(client, '/register', name=name, email=f'{name}@example.com', password='password123')
            self.assertEqual(response.status_code, 302)

    def tearDown(self):
        Path(self.path).unlink(missing_ok=True)

    def post(self, client, path, **data):
        client.get('/')
        with client.session_transaction() as session:
            data['csrf'] = session['csrf']
        return client.post(path, data=data)

    def scalar(self, sql, values=()):
        with closing(sqlite3.connect(self.path)) as connection:
            return connection.execute(sql, values).fetchone()[0]

    def group(self, kind='community'):
        response = self.post(self.owner, '/groups', name='Test runners', sport='Running', location='Sofia', description='Run together', kind=kind)
        self.assertEqual(response.status_code, 302)
        return self.scalar('SELECT MAX(id) FROM groups')

    def session_data(self, group_id):
        return dict(group_id=group_id, title='Interval session', location='Track',
                    starts_at=(datetime.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M'),
                    minutes=60, capacity=1, description='Easy warm-up and intervals')

    def test_pages_and_login(self):
        for path in ['/', '/workouts', '/groups', '/events', '/training']:
            self.assertEqual(self.owner.get(path).status_code, 200)
        self.post(self.owner, '/logout')
        self.assertEqual(self.owner.get('/workouts').status_code, 302)
        self.post(self.owner, '/login', email='owner@example.com', password='wrong')
        self.assertEqual(self.owner.get('/workouts').status_code, 302)
        self.post(self.owner, '/login', email='owner@example.com', password='password123')
        self.assertEqual(self.owner.get('/workouts').status_code, 200)

    def test_csrf_and_duplicate_account(self):
        self.assertEqual(self.owner.post('/logout').status_code, 400)
        response = self.post(self.outsider, '/register', name='Duplicate', email='owner@example.com', password='password123')
        self.assertIn(b'already registered', response.data)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM users'), 3)

    def test_workout_ownership_validation_and_statistics(self):
        data = dict(title='Morning run', sport='Running', minutes=35, activity_date=date.today().isoformat(), notes='<script>alert(1)</script>')
        self.post(self.owner, '/workouts', **data)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM workouts'), 1)
        html = self.owner.get('/workouts').data
        self.assertIn(b'&lt;script&gt;', html)
        self.assertNotIn(b'Morning run', self.member.get('/workouts').data)
        self.assertEqual(self.post(self.member, '/workouts/1/delete').status_code, 404)
        self.post(self.owner, '/workouts', **{**data, 'minutes': -1})
        self.post(self.owner, '/workouts', **{**data, 'activity_date': (date.today() + timedelta(days=1)).isoformat()})
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM workouts'), 1)
        self.assertIn(b'35', self.owner.get('/').data)
        self.post(self.owner, '/workouts/1/delete')
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM workouts'), 0)

    def test_private_groups_require_invitation(self):
        group_id = self.group('friends')
        self.assertNotIn(b'Test runners', self.member.get('/groups').data)
        self.assertNotIn(b'Test runners', self.member.get('/').data)
        self.assertEqual(self.member.get(f'/groups/{group_id}').status_code, 404)
        self.assertEqual(self.post(self.member, f'/groups/{group_id}/membership').status_code, 404)
        code = self.scalar('SELECT invite_code FROM group_settings WHERE group_id=?', (group_id,))
        self.post(self.member, '/groups/invite', invite_code=code)
        self.assertEqual(self.member.get(f'/groups/{group_id}').status_code, 200)
        self.assertIn(b'Test runners', self.member.get('/groups').data)

    def test_scheduling_permission_and_capacity(self):
        group_id = self.group('club')
        self.post(self.member, f'/groups/{group_id}/membership')
        data = self.session_data(group_id)
        self.assertEqual(self.post(self.member, '/training', **data).status_code, 403)
        self.assertEqual(self.post(self.member, f'/groups/{group_id}/permissions/2', action='grant').status_code, 404)
        self.post(self.owner, f'/groups/{group_id}/permissions/2', action='grant')
        self.assertEqual(self.post(self.member, '/training', **data).status_code, 302)
        self.assertNotIn(b'Interval session', self.outsider.get('/training').data)
        self.assertEqual(self.post(self.outsider, '/training/1/reserve').status_code, 404)
        self.post(self.owner, '/training/1/reserve')
        self.post(self.member, '/training/1/reserve')
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM training_reservations'), 1)
        self.post(self.owner, '/training/1/reserve', action='cancel')
        self.post(self.member, '/training/1/reserve')
        self.assertEqual(self.scalar('SELECT user_id FROM training_reservations'), 2)
        self.post(self.owner, f'/groups/{group_id}/permissions/2', action='revoke')
        self.assertEqual(self.post(self.member, '/training', **data).status_code, 403)

    def test_leaving_removes_reservations_and_permissions(self):
        group_id = self.group()
        self.post(self.member, f'/groups/{group_id}/membership')
        self.post(self.owner, f'/groups/{group_id}/permissions/2', action='grant')
        self.post(self.member, '/training', **self.session_data(group_id))
        self.post(self.member, '/training/1/reserve')
        self.post(self.member, f'/groups/{group_id}/membership', action='leave')
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM scheduling_permissions'), 0)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM training_reservations'), 0)
        self.post(self.owner, f'/groups/{group_id}/membership', action='leave')
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM memberships'), 1)

    def test_event_capacity_duplicate_and_cancellation(self):
        self.post(self.owner, '/events', title='Park run', sport='Running', location='Park', capacity=1,
                  starts_at=(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'), description='All welcome')
        self.post(self.owner, '/events/1/rsvp')
        self.post(self.owner, '/events/1/rsvp')
        self.post(self.member, '/events/1/rsvp')
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM rsvps'), 1)
        self.post(self.owner, '/events/1/rsvp', action='cancel')
        self.post(self.member, '/events/1/rsvp')
        self.assertEqual(self.scalar('SELECT user_id FROM rsvps'), 2)

    def test_language_switch_and_redirect_safety(self):
        response = self.post(self.owner, '/language', language='bg', next='/groups')
        self.assertEqual(response.location, '/groups')
        self.assertIn('Групи', self.owner.get('/groups').data.decode())
        for target in ['//example.com', 'https://example.com', '/\\example.com']:
            self.assertEqual(self.post(self.owner, '/language', language='en', next=target).location, '/')

    def test_registration_preserves_locale_and_password_spaces(self):
        client = self.app.test_client()
        self.post(client, '/language', language='bg')
        self.post(client, '/register', name='New member', email='new@example.com', password=' password123 ')
        with client.session_transaction() as session:
            self.assertEqual(session['language'], 'bg')
        self.post(client, '/logout')
        self.post(client, '/login', email='new@example.com', password=' password123 ')
        self.assertEqual(client.get('/workouts').status_code, 200)
        response = self.post(client, '/workouts', title='Run', sport='Running', minutes=30, activity_date='invalid')
        self.assertIn('Въведи валидна дата.', response.data.decode())


if __name__ == '__main__':
    unittest.main()
