"""Personal completed workout logs, validation, and ownership checks."""
from datetime import date
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from flask_babel import gettext as _
from .core import db, login_required, field, sport, number, date_field

bp = Blueprint('workouts', __name__)

@bp.route('/workouts', methods=['GET', 'POST'])
@login_required
def workouts():
    if request.method == 'POST':
        try:
            title, activity_sport, minutes = field('title', 100), sport(), number('minutes', 1440)
            activity_date = date_field('activity_date')
            if activity_date > date.today():
                raise ValueError(_('Workout dates cannot be in the future.'))
            notes = request.form.get('notes', '').strip()
            visibility = request.form.get('visibility', 'private')
            if visibility not in ('private', 'public'):
                raise ValueError(_('Choose a valid visibility.'))
            if len(notes) > 2000:
                raise ValueError(_('Notes must be under 2000 characters.'))
            db().execute('INSERT INTO workouts(user_id,title,sport,minutes,activity_date,notes,public) VALUES(?,?,?,?,?,?,?)',
                         (g.user['id'], title, activity_sport, minutes, activity_date.isoformat(), notes, visibility == 'public'))
            db().commit()
            flash(_('Workout saved. Keep it up!'), 'success')
            return redirect(url_for('workouts.workouts'))
        except ValueError as error:
            flash(str(error), 'error')
    rows = db().execute('SELECT * FROM workouts WHERE user_id=? ORDER BY activity_date DESC,id DESC', (g.user['id'],)).fetchall()
    return render_template('workouts.html', activities=rows)


@bp.post('/workouts/<int:workout_id>/visibility')
@login_required
def visibility(workout_id):
    value = request.form.get('visibility')
    if value not in ('private', 'public'):
        abort(400)
    cursor = db().execute('UPDATE workouts SET public=? WHERE id=? AND user_id=?',
                          (value == 'public', workout_id, g.user['id']))
    if not cursor.rowcount:
        abort(404)
    db().commit()
    return redirect(url_for('workouts.workouts'))

@bp.post('/workouts/<int:workout_id>/delete')
@login_required
def delete_workout(workout_id):
    cursor = db().execute('DELETE FROM workouts WHERE id=? AND user_id=?', (workout_id, g.user['id']))
    if not cursor.rowcount:
        abort(404)
    db().commit()
    flash(_('Workout deleted.'), 'success')
    return redirect(url_for('workouts.workouts'))

