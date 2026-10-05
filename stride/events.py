"""Public event discovery, creation, and capacity-limited RSVPs."""
from datetime import datetime
from flask import Blueprint, abort, flash, g, redirect, render_template, request, session, url_for
from flask_babel import gettext as _
from .core import db, login_required, field, sport, number, datetime_field

bp = Blueprint('events', __name__)

def event_rows():
    return db().execute('''SELECT events.*, (SELECT COUNT(*) FROM rsvps WHERE event_id=events.id) AS attendees,
       EXISTS(SELECT 1 FROM rsvps WHERE event_id=events.id AND user_id=?) AS joined FROM events
       WHERE starts_at >= ? ORDER BY starts_at''', (session.get('user_id'), datetime.now().strftime('%Y-%m-%dT%H:%M'))).fetchall()


@bp.route('/events', methods=['GET', 'POST'])
def events():
    if request.method == 'POST':
        if not g.user:
            return redirect(url_for('accounts.login'))
        try:
            title, activity_sport, location = field('title', 100), sport(), field('location', 160)
            starts_at = datetime_field('starts_at')
            if starts_at.tzinfo or starts_at <= datetime.now():
                raise ValueError(_('Choose a future local date and time.'))
            capacity, description = number('capacity', 10000), field('description', 2000)
            db().execute('INSERT INTO events(owner_id,title,sport,location,starts_at,capacity,description) VALUES(?,?,?,?,?,?,?)',
                         (g.user['id'], title, activity_sport, location, starts_at.isoformat(timespec='minutes'), capacity, description))
            db().commit()
            flash(_('Event created. Invite your community!'), 'success')
            return redirect(url_for('events.events'))
        except ValueError as error:
            flash(str(error), 'error')
    return render_template('events.html', events=event_rows())

@bp.post('/events/<int:event_id>/rsvp')
@login_required
def rsvp(event_id):
    # Serialize capacity checks and reservations to prevent overbooking.
    db().execute('BEGIN IMMEDIATE')
    event = db().execute('SELECT * FROM events WHERE id=?', (event_id,)).fetchone()
    if not event:
        abort(404)
    if request.form.get('action') == 'cancel':
        db().execute('DELETE FROM rsvps WHERE user_id=? AND event_id=?', (g.user['id'], event_id))
        flash(_('Your RSVP was cancelled.'), 'success')
    elif event['starts_at'] <= datetime.now().strftime('%Y-%m-%dT%H:%M'):
        flash(_('This event has already started.'), 'error')
    elif db().execute('SELECT 1 FROM rsvps WHERE user_id=? AND event_id=?', (g.user['id'], event_id)).fetchone():
        flash(_('You are already going.'), 'info')
    elif db().execute('SELECT COUNT(*) FROM rsvps WHERE event_id=?', (event_id,)).fetchone()[0] >= event['capacity']:
        flash(_('This event is full.'), 'error')
    else:
        db().execute('INSERT INTO rsvps VALUES(?,?)', (g.user['id'], event_id))
        flash(_('You are on the list. See you there!'), 'success')
    db().commit()
    return redirect(url_for('events.events'))

