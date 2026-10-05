import sqlite3
import unittest
import uuid
from contextlib import closing
from datetime import datetime
from pathlib import Path

from werkzeug.security import check_password_hash

from stride import create_app
from stride.database import db
from stride.demo import DEMO_PASSWORD, seed_demo


class DemoTests(unittest.TestCase):
    def setUp(self):
        self.path = Path(__file__).resolve().parents[1] / 'instance' / f'test-{uuid.uuid4().hex}.sqlite'
        self.app = create_app({'TESTING': True, 'SECRET_KEY': 'test-key', 'DATABASE': str(self.path)})

    def tearDown(self):
        self.path.unlink(missing_ok=True)

    def test_seed_relationships_login_and_repeat_run(self):
        with self.app.app_context():
            connection = db()
            connection.execute('INSERT INTO users(name,email,password_hash) VALUES(?,?,?)',
                               ('Existing User', 'existing@example.com', 'unchanged'))
            connection.commit()
            self.assertTrue(seed_demo(datetime(2026, 10, 5, 23, 59)))
            for table, expected in [('users', 29), ('workouts', 168), ('groups', 7),
                                    ('training_sessions', 56), ('events', 28),
                                    ('memberships', 28), ('training_reservations', 224), ('rsvps', 168)]:
                self.assertEqual(connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0], expected)
            self.assertEqual(connection.execute('PRAGMA foreign_key_check').fetchall(), [])
            users = connection.execute("SELECT * FROM users WHERE email LIKE '%@demo.example'").fetchall()
            for user in users:
                self.assertTrue(check_password_hash(user['password_hash'], DEMO_PASSWORD))
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM workouts WHERE user_id=?', (user['id'],)).fetchone()[0], 6)
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM training_sessions WHERE creator_id=?', (user['id'],)).fetchone()[0], 2)
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM events WHERE owner_id=?', (user['id'],)).fetchone()[0], 1)
            self.assertEqual(connection.execute('''SELECT COUNT(*) FROM training_reservations r
                JOIN training_sessions s ON s.id=r.session_id
                LEFT JOIN memberships m ON m.user_id=r.user_id AND m.group_id=s.group_id
                WHERE m.user_id IS NULL''').fetchone()[0], 0)
            self.assertEqual(connection.execute('''SELECT COUNT(*) FROM training_sessions s
                JOIN groups g ON g.id=s.group_id WHERE s.creator_id<>g.owner_id AND NOT EXISTS (
                SELECT 1 FROM scheduling_permissions p WHERE p.user_id=s.creator_id AND p.group_id=s.group_id)''').fetchone()[0], 0)
            for table, reservations, key in [('events', 'rsvps', 'event_id'),
                                              ('training_sessions', 'training_reservations', 'session_id')]:
                self.assertEqual(connection.execute(f'''SELECT COUNT(*) FROM {table} t WHERE
                    (SELECT COUNT(*) FROM {reservations} r WHERE r.{key}=t.id)>t.capacity''').fetchone()[0], 0)
                self.assertGreater(connection.execute(f'SELECT MIN(starts_at) FROM {table}').fetchone()[0], '2026-10-05T23:59')
            self.assertLessEqual(connection.execute('SELECT MAX(activity_date) FROM workouts').fetchone()[0], '2026-10-05')
            before = list(connection.iterdump())
            self.assertFalse(seed_demo(datetime(2026, 11, 5)))
            self.assertEqual(list(connection.iterdump()), before)
            self.assertEqual(connection.execute('SELECT password_hash FROM users WHERE id=1').fetchone()[0], 'unchanged')

        client = self.app.test_client()
        client.get('/login')
        with client.session_transaction() as session:
            csrf = session['csrf']
        self.assertEqual(client.post('/login', data={'csrf': csrf, 'email': 'elena.petrova@demo.example',
                                                    'password': DEMO_PASSWORD}).status_code, 302)
        for route in ['/', '/workouts', '/training', '/groups', '/events']:
            self.assertEqual(client.get(route).status_code, 200)
        result = self.app.test_cli_runner().invoke(args=['seed-demo'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('already seeded', result.output)

    def test_collision_rolls_back_whole_dataset(self):
        with self.app.app_context():
            connection = db()
            connection.execute('INSERT INTO users(name,email,password_hash) VALUES(?,?,?)',
                               ('Existing Maya', 'maya.georgieva@demo.example', 'unchanged'))
            connection.commit()
            with self.assertRaises(sqlite3.IntegrityError):
                seed_demo(datetime(2026, 10, 5))
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM users').fetchone()[0], 1)
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM workouts').fetchone()[0], 0)
            self.assertEqual(connection.execute('SELECT password_hash FROM users').fetchone()[0], 'unchanged')
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual(connection.execute('PRAGMA foreign_key_check').fetchall(), [])
