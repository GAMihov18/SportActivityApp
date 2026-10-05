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
        db().commit()
