"""Personal statistics and community overview."""
from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, session
from .database import db

from .groups import group_rows
from .events import event_rows
from .progress import activity_calendar, goal_progress

bp = Blueprint('dashboard', __name__)

@bp.get('/')
def dashboard():
    activities = db().execute('SELECT * FROM workouts WHERE user_id=? ORDER BY activity_date DESC, id DESC LIMIT 5',
                               (session.get('user_id'),)).fetchall()
    monday = date.today() - timedelta(days=date.today().weekday())
    weekly = db().execute('SELECT COUNT(*) AS count, COALESCE(SUM(minutes),0) AS minutes FROM workouts WHERE user_id=? AND activity_date BETWEEN ? AND ?',
                          (session.get('user_id'), monday.isoformat(), date.today().isoformat())).fetchone()
    memberships = db().execute('SELECT COUNT(*) FROM memberships WHERE user_id=?', (session.get('user_id'),)).fetchone()[0]
    rsvps = db().execute('SELECT COUNT(*) FROM rsvps JOIN events ON events.id=rsvps.event_id WHERE user_id=? AND starts_at>=?',
                        (session.get('user_id'), datetime.now().strftime('%Y-%m-%dT%H:%M'))).fetchone()[0]
    return render_template('dashboard.html', activities=activities, weekly=weekly, membership_count=memberships,
                           rsvp_count=rsvps, events=event_rows()[:3], groups=group_rows()[:3],
                           progress=goal_progress(session.get('user_id')),
                           calendar=activity_calendar(session.get('user_id')))

