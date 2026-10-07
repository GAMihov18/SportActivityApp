"""Integration coverage for privacy, goals, friendships and scheduling upgrades."""
import sqlite3
import unittest
from contextlib import closing
from datetime import date, timedelta

import test_app
from stride import create_app
from stride.database import db
from stride.progress import activity_calendar, goal_progress


class FeatureTests(unittest.TestCase):
    setUp = test_app.AppTests.setUp
    tearDown = test_app.AppTests.tearDown
    post = test_app.AppTests.post
    scalar = test_app.AppTests.scalar
    group = test_app.AppTests.group
    session_data = test_app.AppTests.session_data

    def profile_data(self, **overrides):
        return dict(name='Owner', about='I enjoy running', pronouns='they/them',
                    favorite_sport='Running', privacy='public', **overrides)

    def workout(self, **overrides):
        data = dict(title='Hidden workout', sport='Running', minutes=35,
                    activity_date=date.today().isoformat(), notes='Personal notes')
        data.update(overrides)
        return self.post(self.owner, '/workouts', **data)

    def test_profile_privacy_shared_group_and_escaping(self):
        self.assertEqual(self.outsider.get('/profiles/1').status_code, 404)
        group_id = self.group()
        self.post(self.member, f'/groups/{group_id}/membership')
        self.assertEqual(self.member.get('/profiles/1').status_code, 200)
        data = self.profile_data()
        data['about'] = '<script>bad()</script>'
        self.post(self.owner, '/profile/edit', **data)
        anonymous = self.app.test_client()
        html = anonymous.get('/profiles/1').data
        self.assertIn(b'&lt;script&gt;', html)
        self.assertIn(b'they/them', html)
        data['privacy'] = 'private'
        self.post(self.owner, '/profile/edit', **data)
        self.assertEqual(anonymous.get('/profiles/1').status_code, 404)
        self.post(self.member, f'/groups/{group_id}/membership', action='leave')
        self.assertEqual(self.member.get('/profiles/1').status_code, 404)
        self.assertEqual(self.owner.get('/profiles/1').status_code, 200)
        self.assertEqual(self.member.get('/profile/edit').status_code, 200)
        self.assertEqual(self.owner.post('/profile/edit', data=data).status_code, 400)

    def test_workout_visibility_does_not_leak_through_calendar(self):
        self.post(self.owner, '/profile/edit', **self.profile_data())
        self.workout(minutes=999)
        self.workout(title='Visible run', minutes=30, visibility='public', notes='Public notes')
        html = self.outsider.get('/profiles/1').data
        self.assertIn(b'Visible run', html)
        self.assertNotIn(b'Hidden workout', html)
        self.assertNotIn(b'Personal notes', html)
        self.assertNotIn(b'999', html)
        self.assertEqual(self.post(self.member, '/workouts/1/visibility', visibility='public').status_code, 404)
        self.post(self.owner, '/workouts/1/visibility', visibility='public')
        self.assertIn(b'Hidden workout', self.member.get('/profiles/1').data)
        self.post(self.owner, '/workouts/1/visibility', visibility='private')
        self.assertNotIn(b'Hidden workout', self.member.get('/profiles/1').data)
        self.assertEqual(self.post(self.owner, '/workouts/1/visibility', visibility='other').status_code, 400)

    def test_calendar_leap_year_aggregation_and_goals(self):
        self.workout(activity_date='2024-02-29', minutes=30)
        self.workout(activity_date='2024-02-29', minutes=40)
        self.workout(minutes=45)
        self.workout(sport='Cycling', minutes=20)
        self.post(self.owner, '/goals', sport='Running', workouts=3, minutes=150)
        with self.app.test_request_context('/?year=2024'):
            calendar = activity_calendar(1)
            cells = [cell for month in calendar['months'] for week in month['weeks'] for cell in week if not cell['outside']]
            self.assertEqual(len(cells), 366)
            leap = next(cell for cell in cells if cell['date'] == '2024-02-29')
            self.assertEqual((leap['count'], leap['minutes'], leap['level']), (2, 70, 3))
            progress = goal_progress(1)
            self.assertEqual(progress['totals']['workouts'], 1)
            self.assertEqual(progress['totals']['minutes'], 45)
        self.assertEqual(self.owner.get('/?year=invalid').status_code, 200)
        self.assertEqual(self.owner.get('/?year=999999').status_code, 200)
        self.post(self.owner, '/goals', sport='Invalid', workouts=3, minutes=150)
        self.assertEqual(self.scalar('SELECT sport FROM weekly_goals'), 'Running')
        self.post(self.owner, '/goals', sport='', workouts=0, minutes=150)
        self.assertEqual(self.scalar('SELECT workouts FROM weekly_goals'), 3)
        self.post(self.owner, '/goals', sport='', workouts=3, minutes='')
        self.assertIsNone(self.scalar('SELECT minutes FROM weekly_goals'))
        self.post(self.owner, '/goals', sport='', workouts='', minutes=150)
        self.assertIsNone(self.scalar('SELECT workouts FROM weekly_goals'))
        self.post(self.owner, '/goals', sport='', workouts='', minutes='')
        self.assertEqual(self.scalar('SELECT minutes FROM weekly_goals'), 150)
        self.post(self.owner, '/goals', action='remove')
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM weekly_goals'), 0)

    def test_friend_requests_search_and_privacy(self):
        self.assertNotIn(b'href="/profiles/1"', self.member.get('/friends?q=Owner').data)
        self.assertEqual(self.post(self.member, '/friends/1').status_code, 404)
        self.post(self.owner, '/profile/edit', **self.profile_data())
        self.assertIn(b'href="/profiles/1"', self.member.get('/friends?q=Owner').data)
        self.post(self.member, '/friends/1')
        self.post(self.member, '/friends/1')
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM friendships'), 1)
        self.assertEqual(self.post(self.member, '/friends/1', action='accept').status_code, 404)
        self.assertEqual(self.post(self.outsider, '/friends/2', action='accept').status_code, 404)
        self.post(self.owner, '/friends/2', action='accept')
        self.assertEqual(self.scalar('SELECT status FROM friendships'), 'accepted')
        self.post(self.owner, '/profile/edit', **{**self.profile_data(), 'privacy': 'private'})
        self.assertEqual(self.member.get('/profiles/1').status_code, 404)
        self.post(self.member, '/friends/1', action='remove')
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM friendships'), 0)
        self.assertEqual(self.post(self.owner, '/friends/1').status_code, 400)
        self.assertEqual(self.post(self.owner, '/friends/999').status_code, 404)

    def test_weekly_series_independent_reservations_and_cancel(self):
        group_id = self.group()
        self.post(self.member, f'/groups/{group_id}/membership')
        self.post(self.owner, '/training', **self.session_data(group_id), repeat='weekly', occurrences=4)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM training_sessions'), 4)
        self.assertEqual(self.scalar('SELECT COUNT(DISTINCT series_id) FROM training_sessions'), 1)
        self.post(self.member, '/training/1/reserve')
        self.post(self.member, '/training/2/reserve')
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM training_reservations'), 2)
        self.assertEqual(self.post(self.member, '/training/1/cancel', scope='series').status_code, 404)
        self.post(self.owner, '/training/1/cancel')
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM training_reservations'), 1)
        self.assertEqual(self.post(self.member, '/training/1/reserve').status_code, 404)
        self.post(self.owner, '/training/2/cancel', scope='series')
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM training_sessions WHERE cancelled=1'), 4)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM training_reservations'), 0)
        self.assertNotIn(b'Interval session', self.member.get('/training').data)

    def test_training_edit_capacity_permission_and_series_dates(self):
        group_id = self.group()
        for client in (self.member, self.outsider):
            self.post(client, f'/groups/{group_id}/membership')
        data = {**self.session_data(group_id), 'capacity': 2}
        self.post(self.owner, '/training', **data, repeat='weekly', occurrences=2)
        self.post(self.member, '/training/1/reserve')
        self.post(self.outsider, '/training/1/reserve')
        self.assertEqual(self.member.get('/training/1/edit').status_code, 404)
        self.assertEqual(self.post(self.member, '/training/1/edit', **data).status_code, 404)
        self.post(self.owner, '/training/1/edit', **{**data, 'capacity': 1})
        self.assertEqual(self.scalar('SELECT capacity FROM training_sessions WHERE id=1'), 2)
        self.post(self.owner, '/training/1/edit', **{**data, 'title': 'Updated session', 'visibility': 'public'})
        self.assertEqual(self.scalar('SELECT title FROM training_sessions WHERE id=1'), 'Updated session')
        self.assertEqual(self.scalar('SELECT title FROM training_sessions WHERE id=2'), 'Interval session')
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM training_reservations'), 2)
        self.assertEqual(self.owner.get('/training/1/edit').status_code, 200)
        first = self.scalar('SELECT starts_at FROM training_sessions WHERE id=1')
        second = self.scalar('SELECT starts_at FROM training_sessions WHERE id=2')
        from datetime import datetime
        self.assertEqual(datetime.fromisoformat(second) - datetime.fromisoformat(first), timedelta(weeks=1))

    def test_public_training_respects_private_group(self):
        group_id = self.group('private')
        self.post(self.owner, '/profile/edit', **self.profile_data())
        self.post(self.owner, '/training', **self.session_data(group_id), visibility='public')
        self.assertNotIn(b'Interval session', self.outsider.get('/profiles/1').data)
        code = self.scalar('SELECT invite_code FROM group_settings')
        self.post(self.member, '/groups/invite', invite_code=code)
        self.assertIn(b'Interval session', self.member.get('/profiles/1').data)
        self.post(self.owner, '/training/1/edit', **self.session_data(group_id), visibility='private')
        self.assertNotIn(b'Interval session', self.member.get('/profiles/1').data)
        self.assertIn(b'Interval session', self.owner.get('/profiles/1').data)
        self.assertIn(b'Private group', self.owner.get(f'/groups/{group_id}').data)

    def test_public_group_training_on_public_profile(self):
        group_id = self.group()
        self.post(self.owner, '/profile/edit', **self.profile_data())
        self.post(self.owner, '/training', **self.session_data(group_id), visibility='public')
        anonymous = self.app.test_client()
        self.assertIn(b'Interval session', anonymous.get('/profiles/1').data)
        self.assertEqual(self.post(self.outsider, '/training/1/reserve').status_code, 404)
        self.post(self.owner, '/training/1/cancel')
        self.assertNotIn(b'Interval session', anonymous.get('/profiles/1').data)

    def test_event_edit_and_cancel(self):
        data = {**self.session_data(1), 'sport': 'Running', 'capacity': 2}
        self.post(self.owner, '/events', **data)
        self.post(self.member, '/events/1/rsvp')
        self.post(self.outsider, '/events/1/rsvp')
        self.assertEqual(self.member.get('/events/1/edit').status_code, 404)
        self.assertEqual(self.post(self.member, '/events/1/cancel').status_code, 404)
        self.assertEqual(self.owner.get('/events/1/edit').status_code, 200)
        self.post(self.owner, '/events/1/edit', **{**data, 'capacity': 1})
        self.assertEqual(self.scalar('SELECT capacity FROM events'), 2)
        self.post(self.owner, '/events/1/edit', **{**data, 'title': 'New event'})
        self.assertEqual(self.scalar('SELECT title FROM events'), 'New event')
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM rsvps'), 2)
        self.post(self.owner, '/events/1/cancel')
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM rsvps'), 0)
        self.assertNotIn(b'New event', self.member.get('/events').data)
        self.assertEqual(self.post(self.member, '/events/1/rsvp').status_code, 404)

    def test_invalid_recurring_form_does_not_partially_create(self):
        group_id = self.group()
        for extra in [dict(repeat='weekly', occurrences=53), dict(repeat='weekly', occurrences='bad'),
                      dict(repeat='daily'), dict(visibility='bad')]:
            self.post(self.owner, '/training', **self.session_data(group_id), **extra)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM training_sessions'), 0)

    def test_additive_upgrades_preserve_existing_data_and_repeat(self):
        # Simulate an installation from before these additions.
        with closing(sqlite3.connect(self.path)) as connection:
            for table, column in [('workouts', 'public'), ('training_sessions', 'public'),
                                  ('training_sessions', 'cancelled'), ('training_sessions', 'series_id'),
                                  ('events', 'cancelled')]:
                connection.execute(f'ALTER TABLE {table} DROP COLUMN {column}')
            connection.execute("INSERT INTO workouts(user_id,title,sport,minutes,activity_date) VALUES(1,'Legacy','Running',30,'2026-01-01')")
            connection.commit()
        config = {'TESTING': True, 'SECRET_KEY': 'test-key', 'DATABASE': self.path}
        upgraded = create_app(config)
        create_app(config)
        with upgraded.app_context():
            self.assertEqual(db().execute('SELECT COUNT(*) FROM users').fetchone()[0], 3)
            self.assertEqual(db().execute('SELECT public FROM workouts').fetchone()[0], 0)
            self.assertEqual(db().execute('PRAGMA foreign_key_check').fetchall(), [])


if __name__ == '__main__':
    unittest.main()
