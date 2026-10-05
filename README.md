# Stride — Sports Activity Web App

A modular Python web app for personal activity tracking, sports communities, clubs,
and private friend groups. Flask serves both the backend and Jinja HTML frontend;
SQLite persists data. English is the default, with Bulgarian translations via Flask-Babel.

## Contents

- [Run locally](#run-locally)
- [Features](#features)
- [Using the app](#using-the-app)
- [Configuration](#configuration)
- [Pages and actions](#pages-and-actions)
- [Module map](#module-map)
- [Data storage](#data-storage)
- [Tests](#tests)
- [Internationalisation](#internationalisation)
- [Troubleshooting](#troubleshooting)
- [Current scope](#current-scope)

## Run locally

Python 3.11+ is recommended. The Python dependencies are Flask and Flask-Babel;
SQLite is included with Python. No Node.js build or separate database server is required.
Run the following commands from the project directory in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python app.py
```

Open http://127.0.0.1:5000 and create an account. The database is created automatically
in `instance/stride.sqlite`. A fresh database starts empty; optional demo data is available below.
The commands call the virtual environment's Python directly, so activation is unnecessary.
Stop the development server with `Ctrl+C`.

### Mock users and activities

Populate the local database with realistic sample profiles:

```powershell
.\.venv\Scripts\python -m flask --app app seed-demo
```

This adds 28 users, 168 completed workouts, 7 groups covering all supported sports,
56 upcoming training sessions, and 28 upcoming events with reservations and RSVPs.
Each mock profile has six workouts, group membership, permission to schedule training,
two created training sessions, and one created event. Dates are relative to the first
run in Sofia local time. The football friend group is private.

Sign in as `elena.petrova@demo.example` with password `StrideDemo2026!`, or use
any mock user's lowercase first/last name in the same email format. All mock accounts
share this password and use the reserved `demo.example` domain; use them for local demos.
Existing records are preserved. Repeat runs make no changes, including to dates or
passwords. A conflicting demo email aborts the entire seed rather than changing an account.
Seeding is explicit and never runs automatically at application startup.

On Linux or macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

If virtual environment creation cannot bootstrap pip, run
`python -m pip --python .venv install -r requirements.txt` using the system pip.

## Features

- Accounts: register, sign in, sign out; hashed passwords and CSRF-protected forms.
- Workouts: log completed activities with sport, date, duration, and notes; delete your own logs.
- Dashboard: current-week activity statistics, memberships, upcoming event RSVPs.
- Groups: public communities, public clubs, and private friend groups accessed by invite code.
- Memberships: join and leave; private groups are hidden from nonmembers.
- Permissions: owners grant/revoke individual members' permission to schedule training.
- Training: permitted members schedule sessions; group members reserve/cancel places.
- Events: publish public events and RSVP/cancel with capacity enforcement.
- Search and sport filtering, responsive layout, keyboard-accessible dialogs.
- English/Bulgarian interface, localized dates, and translated Python validation messages.

Group owners retain membership to manage permissions. Leaving a group removes its
scheduling permission and training reservations. All private group members can share
its invite code. User-entered descriptions and names are displayed as entered, not translated.

Supported sports are Running, Cycling, Strength, Swimming, Yoga, Football, and Hiking.

## Using the app

1. **Create an account.** Register with your name, a valid email address, and a password
   of 8–128 characters. Registration signs you in automatically. Email addresses are
   stored in lowercase and must be unique.
2. **Log a workout.** Open Workouts and enter a title, sport, activity date, duration,
   and optional notes. Dates must be today or earlier; duration is 1–1,440 minutes.
   Your logs are visible only to you, and you can delete your own entries.
3. **Find or create a group.** Browse public communities and clubs, or create one with
   a sport, location, and description. Choose a friend group for private access.
   To join a private group, enter an invite code shared by an existing member.
4. **Schedule training.** Group owners can schedule immediately. Other members need
   scheduling permission granted by the owner on the group detail page. Sessions
   require a future local date/time, location, description, duration, and capacity.
   Members reserve or cancel their own places from Training.
5. **Create or join an event.** Any signed-in user can publish a public event or RSVP
   to an upcoming event. Event and training capacities range from 1 to 10,000 places;
   creators must reserve a place themselves if they want to attend.
6. **Check the dashboard.** Review workout count and minutes from Monday through today,
   your five most recent workouts, membership count, and upcoming event RSVP count.
   The dashboard also previews up to three upcoming public events and visible groups.

Use the language selector to switch between English and Bulgarian. The choice stays
in your browser session across sign-in and sign-out. Public groups and events can be
browsed without an account; personal workouts and training require sign-in.

## Configuration

`app.py` listens on `127.0.0.1:5000`. It reads these environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `SECRET_KEY` | Generated and saved to `instance/session.key` | Signs Flask session cookies. Set a stable secret for deployment. |
| `FLASK_DEBUG` | Disabled | Set to exactly `1` to enable the development debugger and reloader. |

For local debugging in PowerShell:

```powershell
$env:FLASK_DEBUG = '1'
.\.venv\Scripts\python app.py
```

The factory `stride.create_app(test_config=None)` also accepts Flask configuration
overrides. Tests use this to set `TESTING`, `SECRET_KEY`, and an isolated `DATABASE`
file. `DATABASE` defaults to `instance/stride.sqlite`; it is a factory configuration
key, not an environment variable read by this app. The parent directory of a custom
database path must already exist.

By default, session cookies are HTTP-only with `SameSite=Lax`, and requests are limited
to 64 KiB. There is no `.env` loader; set environment variables in your shell or
deployment environment.

## Pages and actions

These routes serve HTML pages and form submissions; the app does not expose a JSON API.
Every POST request requires the session's CSRF token in a form field named `csrf`.
The supplied templates include it automatically.

| Route | Methods | Purpose / access |
| --- | --- | --- |
| `/` | GET | Dashboard and public discovery previews. |
| `/register` | GET, POST | Register and sign in a new account. |
| `/login` | GET, POST | Sign in an existing account. |
| `/logout` | POST | Clear the current account session. |
| `/workouts` | GET, POST | List or add your workouts; sign-in required. |
| `/workouts/<workout_id>/delete` | POST | Delete your own workout. |
| `/groups` | GET, POST | Browse visible groups or create a group after signing in. |
| `/groups/<group_id>` | GET | Public group detail, or private detail for members. |
| `/groups/invite` | POST | Join by invite code; sign-in required. |
| `/groups/<group_id>/membership` | POST | Join a public group or leave a joined group. |
| `/groups/<group_id>/permissions/<user_id>` | POST | Owner grants or revokes a member's scheduling permission. |
| `/training` | GET, POST | View upcoming sessions in your groups or schedule with permission. |
| `/training/<session_id>/reserve` | POST | Group member reserves or cancels a training place. |
| `/events` | GET, POST | Browse upcoming public events or create one after signing in. |
| `/events/<event_id>/rsvp` | POST | Reserve or cancel an event place; sign-in required. |
| `/language` | POST | Select English or Bulgarian and return to a local page. |

## Module map

| Module | Responsibility |
| --- | --- |
| `stride/__init__.py` | Application factory, configuration, shared request hooks |
| `stride/database.py` | SQLite lifecycle and schema initialization |
| `stride/accounts.py` | Registration, sign-in, sign-out |
| `stride/workouts.py` | Completed workout logs |
| `stride/groups.py` | Group discovery, invitations, memberships, permissions |
| `stride/training.py` | Group schedules and training reservations |
| `stride/events.py` | Public events and RSVPs |
| `stride/dashboard.py` | Overview and personal statistics |
| `stride/i18n.py` | Locale selection and date formatting |
| `stride/core.py` | Shared form validation and access checks |

Feature templates live in `templates/`, reusable components in `templates/macros.html`,
and frontend CSS/JavaScript in `static/`. The entry point `app.py` only starts the app.

Other project files:

| Path | Purpose |
| --- | --- |
| `schema.sql` | Creates the SQLite tables if they do not already exist. |
| `requirements.txt` | Python dependency version ranges. |
| `tests/test_app.py` | Application integration tests using Flask's test client. |
| `babel.cfg` | Gettext extraction settings for Python and Jinja templates. |
| `tools/` | Translation extraction, compilation, and initial catalog bootstrap. |
| `translations/` | Gettext template, Bulgarian catalogs, and bootstrap translation map. |
| `docs/` | Dashboard and registration screenshots. |
| `instance/` | Generated local database and session key; ignored by Git. |

## Data storage

SQLite stores accounts, workouts, groups, memberships, group settings, scheduling
permissions, training sessions, training reservations, public events, and RSVPs.
Passwords are hashed using Werkzeug; plaintext passwords are not stored.
Request-scoped connections enable foreign key checks and close after each request.
Capacity checks and reservation inserts run inside `BEGIN IMMEDIATE` transactions
to serialize competing reservations.

Startup executes `schema.sql` with `CREATE TABLE IF NOT EXISTS`, preserving existing
records. There is no versioned migration system: changes to existing table definitions
need a separate migration rather than merely editing the schema file.

For a local backup, stop the server and copy `instance/stride.sqlite` to a safe location.
Keep `instance/session.key` stable to preserve session signing across restarts. To
restore, stop the server and replace the database with your backup before restarting.

## Tests

```powershell
.\.venv\Scripts\python -m unittest discover -s tests -v
```

Tests use isolated SQLite files and cover authentication, CSRF, ownership, private-group
access, permissions, membership cleanup, reservation capacity, and language switching.
Each test creates a separate `instance/test-<unique-id>.sqlite` database and removes it
afterward; the normal application database is not used. On Linux/macOS, use
`.venv/bin/python -m unittest discover -s tests -v`.

## Internationalisation

Python and templates use gettext (`_()`). The language switch stores the locale in the
session. The Bulgarian catalog is `translations/bg/LC_MESSAGES/messages.po`; compiled
`messages.mo` is included so a fresh checkout works without a build step.

After adding strings or changing translations:

```powershell
.\.venv\Scripts\python tools\build_translations.py
.\.venv\Scripts\pybabel update -i translations\messages.pot -d translations
# Translate new entries in messages.po, removing fuzzy flags after review.
.\.venv\Scripts\pybabel compile -d translations
```

`translations/bg.json` and `tools/init_catalog.py` record the initial catalog bootstrap.
Running the bootstrap overwrites the PO catalog; use normal gettext updates for future edits.
New languages can be initialized with `pybabel init` and added to `stride/i18n.py` and
the language selector. Translate sport labels too, since they are looked up dynamically.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| `ModuleNotFoundError` for Flask or Flask-Babel | Install `requirements.txt` with the same virtual environment Python used to start the app. |
| Port 5000 is already in use | Stop the other process, or use `.\.venv\Scripts\python -m flask --app stride:create_app run --port 5001` for an alternate local port. |
| `unable to open database file` | Ensure the database's parent directory exists and is writable. The default `instance/` directory is created automatically. |
| A form returns HTTP 400 after signing in elsewhere or restarting | Reload the page to obtain the current session's CSRF token and submit again. |
| A private group or training session returns HTTP 404 | Confirm that you are signed in as a member of the relevant group. Private resources are hidden from nonmembers. |
| You cannot schedule training | Join the group and ask its owner to grant scheduling permission. |
| Bulgarian strings stay in English after editing the PO file | Compile the catalog with `.\.venv\Scripts\pybabel compile -d translations` and restart the server. |

## Current scope

This is a local working first version. Event/session times currently use the server's
local time; run it in the community's time zone. Cross-time-zone scheduling needs a
stored IANA time zone before international deployment. Language selection is independent
of time zone. Payments, email invitations, reminders, recurring sessions, attendance
tracking, profile editing, and event/session editing/cancellation are not yet implemented.

For deployment, use a production WSGI server with HTTPS, a stable `SECRET_KEY` environment
variable, secure cookies, backups, and login/invite rate limiting. The local session key is
persisted in the ignored `instance/` folder. Debug mode is off by default.
