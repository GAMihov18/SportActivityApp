"""Explicit, transactional sample data for local demonstrations."""
from datetime import datetime, timedelta

import click
from babel.dates import get_timezone
from werkzeug.security import generate_password_hash

from .core import SPORTS
from .database import db

DEMO_PASSWORD = 'StrideDemo2026!'
SEED_KEY = 'demo-v1'
NAMES = (
    'Elena Petrova', 'Nikolay Ivanov', 'Maya Georgieva', 'Daniel Dimitrov',
    'Sofia Marinova', 'Alex Petrov', 'Victoria Koleva', 'Martin Stoyanov',
    'Anna Williams', 'Oliver Smith', 'Emma Garcia', 'Lucas Martin',
    'Amelia Brown', 'Noah Wilson', 'Isabella Rossi', 'Leo Costa',
    'Daria Popova', 'Adam Novak', 'Sara Jensen', 'Tom Becker',
    'Lily Chen', 'Ethan Park', 'Chloe Dubois', 'Hugo Bernard',
    'Zara Ali', 'Omar Hassan', 'Eva Novak', 'Max Fischer',
)
# One community per sport, including a private group.
GROUPS = (
    ('Borisova Garden Runners', 'Borisova Garden, Sofia', 'community'),
    ('Sofia Cycling Club', 'South Park, Sofia', 'club'),
    ('City Strength Crew', 'Training studio, Sofia', 'club'),
    ('Blue Lane Swimmers', 'Spartak Pool, Sofia', 'club'),
    ('Sunrise Yoga Circle', 'South Park, Sofia', 'community'),
    ('Five-a-side Friends', 'Football pitches, Sofia', 'friends'),
    ('Vitosha Trail Community', 'Boyana, Sofia', 'community'),
)
WORKOUTS = (
    ('Easy park run', 'Tempo run', 'Hill repeats', 'Recovery jog', 'Long run', 'Track intervals'),
    ('Easy city ride', 'Hill climb', 'Cadence drills', 'Recovery spin', 'Weekend ride', 'Bike intervals'),
    ('Full body basics', 'Upper body', 'Lower body', 'Mobility and core', 'Strength circuit', 'Technique practice'),
    ('Easy freestyle', 'Stroke drills', 'Pool intervals', 'Recovery swim', 'Endurance swim', 'Kickboard practice'),
    ('Morning flow', 'Balance practice', 'Vinyasa session', 'Restorative yoga', 'Stretch and breathe', 'Core flow'),
    ('Passing drills', 'Small-sided match', 'Footwork practice', 'Recovery and mobility', 'Friendly match', 'Shooting drills'),
    ('Forest walk', 'Hill trail', 'Trail endurance', 'Easy nature walk', 'Mountain hike', 'Navigation practice'),
)


def seed_demo(now=None):
    """Add the complete dataset once; an error rolls back every inserted row."""
    # App dates are naive local timestamps. Use the demo's Sofia timezone explicitly.
    now = now or datetime.now(get_timezone('Europe/Sofia')).replace(tzinfo=None)
    if now.tzinfo is not None:
        raise ValueError('Use a local date/time without a timezone.')
    connection = db()
    with connection:
        connection.execute('BEGIN IMMEDIATE')
        connection.execute('''CREATE TABLE IF NOT EXISTS demo_seed_runs (
            seed_key TEXT PRIMARY KEY, created_at TEXT NOT NULL)''')
        if connection.execute('SELECT 1 FROM demo_seed_runs WHERE seed_key=?', (SEED_KEY,)).fetchone():
            return False

        users = []
        for index, name in enumerate(NAMES):
            email = f'{name.lower().replace(" ", ".")}@demo.example'
            # A conflicting address fails the transaction rather than modifying an account.
            user_id = connection.execute(
                'INSERT INTO users(name,email,password_hash) VALUES(?,?,?)',
                (name, email, generate_password_hash(DEMO_PASSWORD)),
            ).lastrowid
            users.append(user_id)
            sport_index = index % len(SPORTS)
            for workout_index, title in enumerate(WORKOUTS[sport_index]):
                activity_date = (now.date() - timedelta(days=workout_index * 3 + index % 3)).isoformat()
                connection.execute('''INSERT INTO workouts(user_id,title,sport,minutes,activity_date,notes)
                    VALUES(?,?,?,?,?,?)''', (user_id, title, SPORTS[sport_index],
                    25 + (index * 7 + workout_index * 11) % 96, activity_date,
                    'Demo workout. Warm-up, main session, and a relaxed cooldown.'))

        for sport_index, (name, location, kind) in enumerate(GROUPS):
            members = users[sport_index::len(SPORTS)]
            group_id = connection.execute('''INSERT INTO groups(owner_id,name,sport,location,description)
                VALUES(?,?,?,?,?)''', (members[0], name, SPORTS[sport_index], location,
                'Demo group for friendly practice, steady progress, and meeting training partners.')).lastrowid
            connection.execute('INSERT INTO group_settings(group_id,kind,private,invite_code) VALUES(?,?,?,?)',
                               (group_id, kind, kind == 'friends', f'stride-demo-{sport_index + 1}'))
            for member in members:
                connection.execute('INSERT INTO memberships(user_id,group_id) VALUES(?,?)', (member, group_id))
                if member != members[0]:
                    connection.execute('INSERT INTO scheduling_permissions(user_id,group_id) VALUES(?,?)',
                                       (member, group_id))
            for member_index, member in enumerate(members):
                for session_index in range(2):
                    starts_at = (now + timedelta(days=1 + sport_index + member_index * 2 + session_index * 14)).replace(
                        hour=9 if session_index == 0 else 18, minute=0, second=0, microsecond=0)
                    session_id = connection.execute('''INSERT INTO training_sessions(
                        group_id,creator_id,title,starts_at,minutes,capacity,location,description)
                        VALUES(?,?,?,?,?,?,?,?)''', (group_id, member,
                        f'{SPORTS[sport_index]} {"fundamentals" if session_index == 0 else "endurance"} with {NAMES[sport_index + member_index * 7].split()[0]}',
                        starts_at.isoformat(timespec='minutes'), 45 + session_index * 15,
                        8 + sport_index * 2, location,
                        'Demo training: guided warm-up, focused practice, and cooldown. All levels welcome.')).lastrowid
                    for attendee in members:
                        connection.execute('INSERT INTO training_reservations(user_id,session_id) VALUES(?,?)',
                                           (attendee, session_id))

        for index, owner in enumerate(users):
            sport_index = index % len(SPORTS)
            starts_at = (now + timedelta(days=3 + index)).replace(hour=10 + index % 6, minute=0, second=0, microsecond=0)
            event_id = connection.execute('''INSERT INTO events(owner_id,title,sport,location,starts_at,capacity,description)
                VALUES(?,?,?,?,?,?,?)''', (owner,
                f'{SPORTS[sport_index]} {("social meetup", "skills workshop", "weekend challenge", "beginners day")[index // 7]}',
                SPORTS[sport_index], GROUPS[sport_index][1], starts_at.isoformat(timespec='minutes'),
                12 + index % 5 * 6,
                'Demo event. Meet other local athletes for a welcoming session followed by a chance to chat.')).lastrowid
            for offset in range(6):
                connection.execute('INSERT INTO rsvps(user_id,event_id) VALUES(?,?)',
                                   (users[(index + offset) % len(users)], event_id))
        connection.execute('INSERT INTO demo_seed_runs(seed_key,created_at) VALUES(?,?)',
                           (SEED_KEY, now.isoformat(timespec='seconds')))
    return True


def init_app(app):
    @app.cli.command('seed-demo')
    def seed_demo_command():
        """Populate the configured database with mock profiles and sports activities."""
        if seed_demo():
            click.echo('Added 28 demo users, 168 workouts, 7 groups, 56 training sessions, and 28 events.')
            click.echo(f'Demo login: elena.petrova@demo.example / {DEMO_PASSWORD}')
        else:
            click.echo('Demo data is already seeded; no changes made.')
