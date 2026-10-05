CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
 password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workouts (
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
 title TEXT NOT NULL, sport TEXT NOT NULL, minutes INTEGER NOT NULL CHECK(minutes BETWEEN 1 AND 1440),
 activity_date TEXT NOT NULL, notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS groups (
 id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL REFERENCES users(id),
 name TEXT NOT NULL, sport TEXT NOT NULL, location TEXT NOT NULL, description TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memberships (
 user_id INTEGER REFERENCES users(id), group_id INTEGER REFERENCES groups(id),
 PRIMARY KEY(user_id, group_id)
);
CREATE TABLE IF NOT EXISTS events (
 id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL REFERENCES users(id),
 title TEXT NOT NULL, sport TEXT NOT NULL, location TEXT NOT NULL,
 starts_at TEXT NOT NULL, capacity INTEGER NOT NULL CHECK(capacity BETWEEN 1 AND 10000), description TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rsvps (
 user_id INTEGER REFERENCES users(id), event_id INTEGER REFERENCES events(id),
 PRIMARY KEY(user_id, event_id)
);
CREATE TABLE IF NOT EXISTS group_settings (
 group_id INTEGER PRIMARY KEY REFERENCES groups(id), kind TEXT NOT NULL,
 private INTEGER NOT NULL DEFAULT 0, invite_code TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS scheduling_permissions (
 user_id INTEGER NOT NULL, group_id INTEGER NOT NULL,
 PRIMARY KEY(user_id, group_id),
 FOREIGN KEY(user_id, group_id) REFERENCES memberships(user_id, group_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS training_sessions (
 id INTEGER PRIMARY KEY, group_id INTEGER NOT NULL REFERENCES groups(id),
 creator_id INTEGER NOT NULL REFERENCES users(id), title TEXT NOT NULL,
 starts_at TEXT NOT NULL, minutes INTEGER NOT NULL CHECK(minutes BETWEEN 1 AND 1440),
 capacity INTEGER NOT NULL CHECK(capacity BETWEEN 1 AND 10000), location TEXT NOT NULL,
 description TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS training_reservations (
 user_id INTEGER REFERENCES users(id), session_id INTEGER REFERENCES training_sessions(id),
 PRIMARY KEY(user_id, session_id)
);
