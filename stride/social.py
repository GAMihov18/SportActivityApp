"""Profiles and reciprocal friendships with explicit privacy checks."""
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from flask_babel import gettext as _
from .core import SPORTS, db, field, login_required
from .progress import activity_calendar

bp = Blueprint('social', __name__)


def visible_profile(user_id):
    person = db().execute('''SELECT users.id, users.name, COALESCE(profiles.about,'') AS about,
        COALESCE(profiles.pronouns,'') AS pronouns, COALESCE(profiles.favorite_sport,'') AS favorite_sport,
        COALESCE(profiles.private,1) AS private FROM users LEFT JOIN profiles ON profiles.user_id=users.id
        WHERE users.id=?''', (user_id,)).fetchone()
    if not person:
        return None
    if not person['private'] or (g.user and g.user['id'] == user_id):
        return person
    if g.user and db().execute('''SELECT 1 FROM memberships a JOIN memberships b ON a.group_id=b.group_id
        WHERE a.user_id=? AND b.user_id=?''', (g.user['id'], user_id)).fetchone():
        return person
    return None


@bp.get('/profile')
@login_required
def mine():
    return redirect(url_for('social.profile', user_id=g.user['id']))


@bp.get('/profiles/<int:user_id>')
def profile(user_id):
    person = visible_profile(user_id)
    if not person:
        abort(404)
    own = bool(g.user and g.user['id'] == user_id)
    workouts = db().execute('SELECT * FROM workouts WHERE user_id=?'
                            + ('' if own else ' AND public=1') + ' ORDER BY activity_date DESC,id DESC',
                            (user_id,)).fetchall()
    # Publishing a session never reveals a private group's details to outsiders.
    training = db().execute('''SELECT t.*, groups.name AS group_name FROM training_sessions t
        JOIN groups ON groups.id=t.group_id LEFT JOIN group_settings s ON s.group_id=t.group_id
        WHERE t.creator_id=? AND t.cancelled=0 AND (? OR t.public=1)
        AND (COALESCE(s.private,0)=0 OR EXISTS(SELECT 1 FROM memberships WHERE group_id=t.group_id AND user_id=?))
        ORDER BY t.starts_at DESC''', (user_id, own, g.user['id'] if g.user else None)).fetchall()
    relation = None
    if g.user and not own:
        low, high = sorted((g.user['id'], user_id))
        relation = db().execute('SELECT * FROM friendships WHERE user_low=? AND user_high=?', (low, high)).fetchone()
    return render_template('profile.html', person=person, own=own, activities=workouts, training=training,
                           relation=relation, calendar=activity_calendar(user_id, public_only=not own))


@bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit():
    if request.method == 'POST':
        try:
            name = field('name', 100)
            about, pronouns = request.form.get('about', '').strip(), request.form.get('pronouns', '').strip()
            favorite = request.form.get('favorite_sport', '')
            privacy = request.form.get('privacy', 'private')
            if len(about) > 2000 or len(pronouns) > 80:
                raise ValueError(_('Please fill in all fields within their length limits.'))
            if favorite and favorite not in SPORTS:
                raise ValueError(_('Choose a valid sport.'))
            if privacy not in ('public', 'private'):
                raise ValueError(_('Choose a valid visibility.'))
            db().execute('UPDATE users SET name=? WHERE id=?', (name, g.user['id']))
            db().execute('''INSERT INTO profiles VALUES(?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET
                about=excluded.about, pronouns=excluded.pronouns, favorite_sport=excluded.favorite_sport,
                private=excluded.private''', (g.user['id'], about, pronouns, favorite, privacy == 'private'))
            db().commit()
            flash(_('Profile saved.'), 'success')
            return redirect(url_for('social.mine'))
        except ValueError as error:
            flash(str(error), 'error')
    return render_template('profile_edit.html', person=visible_profile(g.user['id']))


@bp.get('/friends')
@login_required
def friends():
    relations = db().execute('''SELECT f.*, users.id, users.name FROM friendships f JOIN users
        ON users.id=CASE WHEN f.user_low=? THEN f.user_high ELSE f.user_low END
        WHERE f.user_low=? OR f.user_high=? ORDER BY users.name''', (g.user['id'],) * 3).fetchall()
    query = request.args.get('q', '').strip()[:100]
    people = []
    if query:
        people = db().execute('''SELECT users.id,users.name FROM users LEFT JOIN profiles p ON p.user_id=users.id
            WHERE users.id!=? AND instr(lower(users.name),lower(?))>0 AND (COALESCE(p.private,1)=0 OR EXISTS(
            SELECT 1 FROM memberships a JOIN memberships b ON a.group_id=b.group_id
            WHERE a.user_id=users.id AND b.user_id=?)) ORDER BY users.name LIMIT 50''',
            (g.user['id'], query, g.user['id'])).fetchall()
    return render_template('friends.html', relations=relations, people=people, query=query)


@bp.post('/friends/<int:user_id>')
@login_required
def friendship(user_id):
    if user_id == g.user['id']:
        abort(400)
    low, high = sorted((user_id, g.user['id']))
    db().execute('BEGIN IMMEDIATE')
    relation = db().execute('SELECT * FROM friendships WHERE user_low=? AND user_high=?', (low, high)).fetchone()
    action = request.form.get('action', 'request')
    if action == 'remove' and relation:
        db().execute('DELETE FROM friendships WHERE user_low=? AND user_high=?', (low, high))
    elif action == 'accept' and relation and relation['status'] == 'pending' and relation['requester_id'] == user_id:
        db().execute("UPDATE friendships SET status='accepted' WHERE user_low=? AND user_high=?", (low, high))
    elif action == 'request' and visible_profile(user_id):
        db().execute("INSERT OR IGNORE INTO friendships VALUES(?,?,?,'pending')", (low, high, g.user['id']))
    else:
        abort(404)
    db().commit()
    flash(_('Friends list updated.'), 'success')
    return redirect(url_for('social.friends'))
