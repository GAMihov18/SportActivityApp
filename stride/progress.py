"""Weekly goals and calendar activity, always scoped to visible workouts."""
import calendar
from datetime import date, timedelta
from flask import Blueprint, flash, g, redirect, request, url_for
from flask_babel import gettext as _
from .core import SPORTS, db, login_required, number

bp = Blueprint('progress', __name__)


def activity_calendar(user_id, public_only=False):
    try:
        year = int(request.args.get('year', date.today().year))
        if not 1900 <= year <= 2100:
            raise ValueError
    except ValueError:
        year = date.today().year
    rows = db().execute('''SELECT activity_date, COUNT(*) AS count, SUM(minutes) AS minutes
        FROM workouts WHERE user_id=? AND activity_date BETWEEN ? AND ?'''
        + (' AND public=1' if public_only else '') + ' GROUP BY activity_date',
        (user_id, f'{year}-01-01', f'{year}-12-31')).fetchall()
    totals = {row['activity_date']: row for row in rows}
    months = []
    for month in range(1, 13):
        weeks = []
        for week in calendar.Calendar(firstweekday=0).monthdatescalendar(year, month):
            cells = []
            for day in week:
                value = totals.get(day.isoformat())
                cells.append(dict(date=day.isoformat(), day=day.day, outside=day.month != month,
                                  count=value['count'] if value else 0,
                                  minutes=value['minutes'] if value else 0,
                                  level=min(4, (value['minutes'] + 29) // 30) if value else 0))
            weeks.append(cells)
        months.append(dict(date=f'{year}-{month:02d}-01', weeks=weeks))
    return dict(year=year, months=months, total=sum(row['count'] for row in rows))


def goal_progress(user_id):
    goal = db().execute('SELECT * FROM weekly_goals WHERE user_id=?', (user_id,)).fetchone()
    if not goal:
        return None
    monday = date.today() - timedelta(days=date.today().weekday())
    totals = db().execute('''SELECT COUNT(*) AS workouts, COALESCE(SUM(minutes),0) AS minutes
        FROM workouts WHERE user_id=? AND activity_date BETWEEN ? AND ? AND (?='' OR sport=?)''',
        (user_id, monday.isoformat(), date.today().isoformat(), goal['sport'], goal['sport'])).fetchone()
    return dict(goal=goal, totals=totals,
                workout_percent=min(100, round(totals['workouts'] / goal['workouts'] * 100)) if goal['workouts'] else 0,
                minute_percent=min(100, round(totals['minutes'] / goal['minutes'] * 100)) if goal['minutes'] else 0)


@bp.post('/goals')
@login_required
def save_goal():
    if request.form.get('action') == 'remove':
        db().execute('DELETE FROM weekly_goals WHERE user_id=?', (g.user['id'],))
        db().commit()
        return redirect(url_for('dashboard.dashboard'))
    try:
        sport = request.form.get('sport', '')
        if sport and sport not in SPORTS:
            raise ValueError(_('Choose a valid sport.'))
        workouts = number('workouts', 100) if request.form.get('workouts', '').strip() else None
        minutes = number('minutes', 10080) if request.form.get('minutes', '').strip() else None
        if workouts is None and minutes is None:
            raise ValueError(_('Set at least one weekly target.'))
        db().execute('''INSERT INTO weekly_goals VALUES(?,?,?,?) ON CONFLICT(user_id)
            DO UPDATE SET sport=excluded.sport, workouts=excluded.workouts, minutes=excluded.minutes''',
            (g.user['id'], sport, workouts, minutes))
        db().commit()
        flash(_('Weekly goals saved.'), 'success')
    except ValueError as error:
        flash(str(error), 'error')
    return redirect(url_for('dashboard.dashboard'))
