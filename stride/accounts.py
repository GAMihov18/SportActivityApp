"""Account registration, sign-in, and session management."""
import sqlite3
import re
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_babel import gettext as _
from werkzeug.security import check_password_hash, generate_password_hash
from .core import db, field

bp = Blueprint('accounts', __name__)

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            name, email = field('name', 80), field('email', 254).lower()
            password = request.form.get('password', '')
            if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email) or not password.strip() or not 8 <= len(password) <= 128:
                raise ValueError(_('Use a valid email and a password with at least 8 characters.'))
            cursor = db().execute('INSERT INTO users(name, email, password_hash) VALUES (?, ?, ?)',
                                  (name, email, generate_password_hash(password)))
            db().commit()
            language = session.get('language', 'en')
            session.clear()
            session.update(user_id=cursor.lastrowid, language=language)
            return redirect(url_for('dashboard.dashboard'))
        except sqlite3.IntegrityError:
            flash(_('This email is already registered.'), 'error')
        except ValueError as error:
            flash(str(error), 'error')
    return render_template('auth.html', registering=True)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = db().execute('SELECT * FROM users WHERE email = ?', (request.form.get('email', '').strip().lower(),)).fetchone()
        if user and check_password_hash(user['password_hash'], request.form.get('password', '')):
            language = session.get('language', 'en')
            session.clear()
            session.update(user_id=user['id'], language=language)
            return redirect(url_for('dashboard.dashboard'))
        flash(_('Email or password is incorrect.'), 'error')
    return render_template('auth.html', registering=False)

@bp.post('/logout')
def logout():
    language = session.get('language', 'en')
    session.clear()
    session['language'] = language
    return redirect(url_for('dashboard.dashboard'))

