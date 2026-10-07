"""Group training schedules and capacity-limited member reservations."""
from datetime import datetime, timedelta
import uuid
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
            visibility = request.form.get('visibility', 'private')
            if visibility not in ('private', 'public'):
                raise ValueError(_('Choose a valid visibility.'))
            occurrences = number('occurrences', 52) if request.form.get('repeat') == 'weekly' else 1
            if request.form.get('repeat', 'once') not in ('once', 'weekly'):
                raise ValueError(_('Choose a valid repeat schedule.'))
            series_id = uuid.uuid4().hex if occurrences > 1 else None
            for occurrence in range(occurrences):
                start = starts_at + timedelta(weeks=occurrence)
                db().execute('''INSERT INTO training_sessions(group_id,creator_id,title,starts_at,minutes,capacity,location,description,public,series_id)
                    VALUES(?,?,?,?,?,?,?,?,?,?)''', (group_id, g.user['id'], title, start.isoformat(timespec='minutes'), minutes, capacity, location, description, visibility == 'public', series_id))
            db().commit()
            flash(_('Training session scheduled.'), 'success')
            return redirect(url_for('training.training'))
        except ValueError as error:
            db().rollback()
            flash(str(error), 'error')
    groups = db().execute('''SELECT groups.* FROM groups JOIN memberships ON groups.id=memberships.group_id
        WHERE memberships.user_id=?''', (g.user['id'],)).fetchall()
    eligible_groups = [group for group in groups if can_schedule(group['id'])]
    sessions = db().execute('''SELECT training_sessions.*, groups.name AS group_name, groups.sport,
        (SELECT COUNT(*) FROM training_reservations WHERE session_id=training_sessions.id) AS attendees,
        EXISTS(SELECT 1 FROM training_reservations WHERE session_id=training_sessions.id AND user_id=?) AS joined
        FROM training_sessions JOIN groups ON groups.id=training_sessions.group_id
        JOIN memberships ON memberships.group_id=groups.id WHERE memberships.user_id=? AND starts_at>=? AND training_sessions.cancelled=0
        ORDER BY starts_at''', (g.user['id'], g.user['id'], datetime.now().strftime('%Y-%m-%dT%H:%M'))).fetchall()
    manageable = {row['id'] for row in sessions if can_manage(row)}
    return render_template('training.html', sessions=sessions, eligible_groups=eligible_groups, manageable=manageable)


@bp.post('/training/<int:session_id>/reserve')
@login_required
def reserve(session_id):
    db().execute('BEGIN IMMEDIATE')
    training = db().execute('SELECT * FROM training_sessions WHERE id=?', (session_id,)).fetchone()
    if not training or training['cancelled'] or not group_member(training['group_id']):
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


def can_manage(item):
    group = db().execute('SELECT owner_id FROM groups WHERE id=?', (item['group_id'],)).fetchone()
    return bool(g.user and group_member(item['group_id']) and
                (g.user['id'] == group['owner_id'] or
                 (g.user['id'] == item['creator_id'] and can_schedule(item['group_id']))))


@bp.route('/training/<int:session_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(session_id):
    item = db().execute('SELECT * FROM training_sessions WHERE id=?', (session_id,)).fetchone()
    if not item or item['cancelled'] or not can_manage(item):
        abort(404)
    if request.method == 'POST':
        db().execute('BEGIN IMMEDIATE')
        item = db().execute('SELECT * FROM training_sessions WHERE id=?', (session_id,)).fetchone()
        if not item or item['cancelled'] or not can_manage(item):
            abort(404)
        try:
            title, location, description = field('title', 100), field('location', 160), field('description', 2000)
            start = datetime_field('starts_at')
            if start.tzinfo or start <= datetime.now():
                raise ValueError(_('Choose a future local date and time.'))
            minutes, capacity = number('minutes', 1440), number('capacity', 10000)
            visibility = request.form.get('visibility', 'private')
            if visibility not in ('public', 'private'):
                raise ValueError(_('Choose a valid visibility.'))
            attendees = db().execute('SELECT COUNT(*) FROM training_reservations WHERE session_id=?', (session_id,)).fetchone()[0]
            if capacity < attendees:
                raise ValueError(_('Capacity cannot be lower than existing reservations.'))
            db().execute('''UPDATE training_sessions SET title=?,location=?,description=?,starts_at=?,minutes=?,capacity=?,public=?
                WHERE id=?''', (title, location, description, start.isoformat(timespec='minutes'), minutes, capacity, visibility == 'public', session_id))
            db().commit()
            flash(_('Training session updated.'), 'success')
            return redirect(url_for('training.training'))
        except ValueError as error:
            db().rollback()
            flash(str(error), 'error')
    return render_template('schedule_edit.html', item=item, training=True)


@bp.post('/training/<int:session_id>/cancel')
@login_required
def cancel(session_id):
    db().execute('BEGIN IMMEDIATE')
    item = db().execute('SELECT * FROM training_sessions WHERE id=?', (session_id,)).fetchone()
    if not item or not can_manage(item):
        abort(404)
    ids = [session_id]
    if request.form.get('scope') == 'series' and item['series_id']:
        ids = [row['id'] for row in db().execute('''SELECT id FROM training_sessions WHERE series_id=? AND starts_at>=?''',
                (item['series_id'], datetime.now().strftime('%Y-%m-%dT%H:%M')))]
    for target in ids:
        db().execute('UPDATE training_sessions SET cancelled=1 WHERE id=?', (target,))
        db().execute('DELETE FROM training_reservations WHERE session_id=?', (target,))
    db().commit()
    flash(_('Training cancelled. Reservations have been removed.'), 'success')
    return redirect(url_for('training.training'))
