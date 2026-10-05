"""Group discovery, invitation access, and member permissions."""
import secrets
from flask import Blueprint, abort, flash, g, redirect, render_template, request, session, url_for
from flask_babel import gettext as _
from .core import db, login_required, field, sport, group_member, can_schedule

bp = Blueprint('groups', __name__)


def group_rows():
    return db().execute('''SELECT groups.*, COALESCE(settings.kind,'community') AS kind,
       COALESCE(settings.private,0) AS private,
       (SELECT COUNT(*) FROM memberships WHERE group_id=groups.id) AS members,
       EXISTS(SELECT 1 FROM memberships WHERE group_id=groups.id AND user_id=?) AS joined
       FROM groups LEFT JOIN group_settings settings ON settings.group_id=groups.id
       WHERE COALESCE(settings.private,0)=0 OR EXISTS(
         SELECT 1 FROM memberships WHERE group_id=groups.id AND user_id=?) ORDER BY groups.id DESC''',
       (session.get('user_id'), session.get('user_id'))).fetchall()


@bp.route('/groups', methods=['GET', 'POST'])
def groups():
    if request.method == 'POST':
        if not g.user:
            return redirect(url_for('accounts.login'))
        try:
            values = (g.user['id'], field('name', 100), sport(), field('location', 160), field('description', 2000))
            kind = request.form.get('kind', 'community')
            if kind not in ('community', 'club', 'friends'):
                raise ValueError(_('Choose a valid group type.'))
            cursor = db().execute('INSERT INTO groups(owner_id,name,sport,location,description) VALUES(?,?,?,?,?)', values)
            group_id = cursor.lastrowid
            db().execute('INSERT INTO memberships VALUES(?,?)', (g.user['id'], group_id))
            db().execute('INSERT INTO group_settings VALUES(?,?,?,?)',
                         (group_id, kind, kind == 'friends', secrets.token_urlsafe(12)))
            db().commit()
            flash(_('Your group is ready.'), 'success')
            return redirect(url_for('groups.detail', group_id=group_id))
        except ValueError as error:
            db().rollback()
            flash(str(error), 'error')
    return render_template('groups.html', groups=group_rows())


@bp.post('/groups/invite')
@login_required
def join_invite():
    group = db().execute('SELECT group_id FROM group_settings WHERE invite_code=?', (request.form.get('invite_code', '').strip(),)).fetchone()
    if not group:
        flash(_('That invite code is not valid.'), 'error')
        return redirect(url_for('groups.groups'))
    db().execute('INSERT OR IGNORE INTO memberships VALUES(?,?)', (g.user['id'], group['group_id']))
    db().commit()
    flash(_('Welcome to the group!'), 'success')
    return redirect(url_for('groups.detail', group_id=group['group_id']))


@bp.post('/groups/<int:group_id>/membership')
@login_required
def membership(group_id):
    group = db().execute('''SELECT groups.*, COALESCE(settings.private,0) AS private FROM groups
        LEFT JOIN group_settings settings ON settings.group_id=groups.id WHERE groups.id=?''', (group_id,)).fetchone()
    if not group or (group['private'] and not group_member(group_id)):
        abort(404)
    if request.form.get('action') == 'leave':
        if group['owner_id'] == g.user['id']:
            flash(_('Group owners must remain members to manage the group.'), 'error')
            return redirect(url_for('groups.detail', group_id=group_id))
        db().execute('DELETE FROM training_reservations WHERE user_id=? AND session_id IN (SELECT id FROM training_sessions WHERE group_id=?)', (g.user['id'], group_id))
        db().execute('DELETE FROM memberships WHERE user_id=? AND group_id=?', (g.user['id'], group_id))
        flash(_('You left the group.'), 'success')
    else:
        db().execute('INSERT OR IGNORE INTO memberships VALUES(?,?)', (g.user['id'], group_id))
        flash(_('Welcome to the group!'), 'success')
    db().commit()
    return redirect(url_for('groups.groups'))


@bp.get('/groups/<int:group_id>')
def detail(group_id):
    group = db().execute('''SELECT groups.*, COALESCE(settings.kind,'community') AS kind,
       COALESCE(settings.private,0) AS private, settings.invite_code FROM groups
       LEFT JOIN group_settings settings ON settings.group_id=groups.id WHERE groups.id=?''', (group_id,)).fetchone()
    member = group_member(group_id)
    if not group or (group['private'] and not member):
        abort(404)
    members = []
    if member:
        members = db().execute('''SELECT users.id,users.name, EXISTS(SELECT 1 FROM scheduling_permissions
            WHERE user_id=users.id AND group_id=?) AS can_schedule FROM users JOIN memberships ON users.id=memberships.user_id
            WHERE memberships.group_id=? ORDER BY users.name''', (group_id, group_id)).fetchall()
    return render_template('group_detail.html', group=group, members=members, member=member,
                           scheduling=can_schedule(group_id))


@bp.post('/groups/<int:group_id>/permissions/<int:user_id>')
@login_required
def permissions(group_id, user_id):
    group = db().execute('SELECT * FROM groups WHERE id=?', (group_id,)).fetchone()
    if not group or group['owner_id'] != g.user['id']:
        abort(404)
    if user_id == group['owner_id'] or not db().execute('SELECT 1 FROM memberships WHERE user_id=? AND group_id=?', (user_id, group_id)).fetchone():
        abort(400)
    if request.form.get('action') == 'grant':
        db().execute('INSERT OR IGNORE INTO scheduling_permissions VALUES(?,?)', (user_id, group_id))
    else:
        db().execute('DELETE FROM scheduling_permissions WHERE user_id=? AND group_id=?', (user_id, group_id))
    db().commit()
    flash(_('Scheduling permission updated.'), 'success')
    return redirect(url_for('groups.detail', group_id=group_id))
