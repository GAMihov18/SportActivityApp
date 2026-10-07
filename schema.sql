CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
 password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workouts (
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
 title TEXT NOT NULL, sport TEXT NOT NULL, minutes INTEGER NOT NULL CHECK(minutes BETWEEN 1 AND 1440),
 activity_date TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '',
 public INTEGER NOT NULL DEFAULT 0 CHECK(public IN (0,1))
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
 starts_at TEXT NOT NULL, capacity INTEGER NOT NULL CHECK(capacity BETWEEN 1 AND 10000), description TEXT NOT NULL,
 cancelled INTEGER NOT NULL DEFAULT 0
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
 description TEXT NOT NULL, public INTEGER NOT NULL DEFAULT 0 CHECK(public IN (0,1)),
 cancelled INTEGER NOT NULL DEFAULT 0, series_id TEXT
);
CREATE TABLE IF NOT EXISTS training_reservations (
 user_id INTEGER REFERENCES users(id), session_id INTEGER REFERENCES training_sessions(id),
 PRIMARY KEY(user_id, session_id)
);
CREATE TABLE IF NOT EXISTS profiles (
 user_id INTEGER PRIMARY KEY REFERENCES users(id),
 about TEXT NOT NULL DEFAULT '', pronouns TEXT NOT NULL DEFAULT '',
 favorite_sport TEXT NOT NULL DEFAULT '', private INTEGER NOT NULL DEFAULT 1 CHECK(private IN (0,1))
);
CREATE TABLE IF NOT EXISTS weekly_goals (
 user_id INTEGER PRIMARY KEY REFERENCES users(id), sport TEXT NOT NULL DEFAULT '',
 workouts INTEGER CHECK(workouts BETWEEN 1 AND 100),
 minutes INTEGER CHECK(minutes BETWEEN 1 AND 10080),
 CHECK(workouts IS NOT NULL OR minutes IS NOT NULL)
);
CREATE TABLE IF NOT EXISTS friendships (
 user_low INTEGER NOT NULL REFERENCES users(id), user_high INTEGER NOT NULL REFERENCES users(id),
 requester_id INTEGER NOT NULL REFERENCES users(id), status TEXT NOT NULL CHECK(status IN ('pending','accepted')),
 PRIMARY KEY(user_low,user_high), CHECK(user_low < user_high),
 CHECK(requester_id IN (user_low,user_high))
);
