"""Request-scoped SQLite connections and schema initialization."""
import sqlite3
from flask import current_app, g


def db():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


def init_app(app, schema_path):
    @app.teardown_appcontext
    def close_db(error=None):
        connection = g.pop('db', None)
        if connection:
            connection.close()

    with app.app_context():
        db().executescript(schema_path.read_text(encoding='utf-8'))
        db().execute('BEGIN IMMEDIATE')
        # Additive upgrades preserve existing installations and their private logs.
        for table, additions in {
            'workouts': {'public': 'INTEGER NOT NULL DEFAULT 0 CHECK(public IN (0,1))'},
            'training_sessions': {'public': 'INTEGER NOT NULL DEFAULT 0 CHECK(public IN (0,1))',
                                  'cancelled': 'INTEGER NOT NULL DEFAULT 0', 'series_id': 'TEXT'},
            'events': {'cancelled': 'INTEGER NOT NULL DEFAULT 0'},
        }.items():
            columns = {row['name'] for row in db().execute(f'PRAGMA table_info({table})')}
            for name, definition in additions.items():
                if name not in columns:
                    db().execute(f'ALTER TABLE {table} ADD COLUMN {name} {definition}')
        db().commit()
