"""Group training schedules and capacity-limited member reservations."""
from datetime import datetime
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from flask_babel import gettext as _
from .core import db, login_required, field, number, can_schedule, group_member, datetime_field

bp = Blueprint('training', __name__)


@bp.route('/training', methods=['GET', 'POST'])
@login_required
def training():
    if request.method == 'POST':
        try:
            group_id = number('group_id', 2147483647)
            if not can_schedule(group_id):
                abort(403)
            title, location = field('title', 100), field('location', 160)
            starts_at = datetime_field('starts_at')
            if starts_at.tzinfo or starts_at <= datetime.now():
                raise ValueError(_('Choose a future local date and time.'))
            minutes, capacity = number('minutes', 1440), number('capacity', 10000)
            description = field('description', 2000)
            db().execute('''INSERT INTO training_sessions(group_id,creator_id,title,starts_at,minutes,capacity,location,description)
                VALUES(?,?,?,?,?,?,?,?)''', (group_id, g.user['id'], title, starts_at.isoformat(timespec='minutes'), minutes, capacity, location, description))
            db().commit()
            flash(_('Training session scheduled.'), 'success')
            return redirect(url_for('training.training'))
        except ValueError as error:
            flash(str(error), 'error')
    groups = db().execute('''SELECT groups.* FROM groups JOIN memberships ON groups.id=memberships.group_id
        WHERE memberships.user_id=?''', (g.user['id'],)).fetchall()
    eligible_groups = [group for group in groups if can_schedule(group['id'])]
    sessions = db().execute('''SELECT training_sessions.*, groups.name AS group_name, groups.sport,
        (SELECT COUNT(*) FROM training_reservations WHERE session_id=training_sessions.id) AS attendees,
        EXISTS(SELECT 1 FROM training_reservations WHERE session_id=training_sessions.id AND user_id=?) AS joined
        FROM training_sessions JOIN groups ON groups.id=training_sessions.group_id
        JOIN memberships ON memberships.group_id=groups.id WHERE memberships.user_id=? AND starts_at>=?
        ORDER BY starts_at''', (g.user['id'], g.user['id'], datetime.now().strftime('%Y-%m-%dT%H:%M'))).fetchall()
    return render_template('training.html', sessions=sessions, eligible_groups=eligible_groups)


@bp.post('/training/<int:session_id>/reserve')
@login_required
def reserve(session_id):
    db().execute('BEGIN IMMEDIATE')
    training = db().execute('SELECT * FROM training_sessions WHERE id=?', (session_id,)).fetchone()
    if not training or not group_member(training['group_id']):
        abort(404)
    if request.form.get('action') == 'cancel':
        db().execute('DELETE FROM training_reservations WHERE user_id=? AND session_id=?', (g.user['id'], session_id))
        flash(_('Reservation cancelled.'), 'success')
    elif training['starts_at'] <= datetime.now().strftime('%Y-%m-%dT%H:%M'):
        flash(_('This session has already started.'), 'error')
    elif db().execute('SELECT 1 FROM training_reservations WHERE user_id=? AND session_id=?', (g.user['id'], session_id)).fetchone():
        flash(_('You are already going.'), 'info')
    elif db().execute('SELECT COUNT(*) FROM training_reservations WHERE session_id=?', (session_id,)).fetchone()[0] >= training['capacity']:
        flash(_('This session is full.'), 'error')
    else:
        db().execute('INSERT INTO training_reservations VALUES(?,?)', (g.user['id'], session_id))
        flash(_('Your training place is reserved.'), 'success')
    db().commit()
    return redirect(url_for('training.training'))
