from datetime import date, datetime
from functools import wraps
from flask import flash, g, redirect, request, url_for
from flask_babel import gettext as _
from .database import db

SPORTS = ('Running', 'Cycling', 'Strength', 'Swimming', 'Yoga', 'Football', 'Hiking')

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.user:
            flash(_('Sign in to continue.'), 'info')
            return redirect(url_for('accounts.login'))
        return view(*args, **kwargs)
    return wrapped

def field(name, maximum=200):
    value = request.form.get(name, '').strip()
    if not value or len(value) > maximum:
        raise ValueError(_('Please fill in all fields within their length limits.'))
    return value


def group_member(group_id):
    return bool(g.user and db().execute('SELECT 1 FROM memberships WHERE user_id=? AND group_id=?',
                                       (g.user['id'], group_id)).fetchone())


def can_schedule(group_id):
    if not group_member(group_id):
        return False
    group = db().execute('SELECT owner_id FROM groups WHERE id=?', (group_id,)).fetchone()
    return bool(group and (group['owner_id'] == g.user['id'] or db().execute(
        'SELECT 1 FROM scheduling_permissions WHERE user_id=? AND group_id=?', (g.user['id'], group_id)).fetchone()))

def sport():
    value = field('sport')
    if value not in SPORTS:
        raise ValueError(_('Choose a valid sport.'))
    return value

def number(name, maximum):
    try:
        value = int(request.form.get(name, ''))
    except ValueError:
        raise ValueError(_('Enter a valid positive number.')) from None
    if not 1 <= value <= maximum:
        raise ValueError(_('Enter a valid positive number.'))
    return value


def date_field(name):
    try:
        return date.fromisoformat(field(name))
    except ValueError:
        raise ValueError(_('Enter a valid date.')) from None


def datetime_field(name):
    try:
        return datetime.fromisoformat(field(name))
    except ValueError:
        raise ValueError(_('Enter a valid date and time.')) from None

