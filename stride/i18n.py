"""Locale selection, gettext integration, and localized date display."""
from datetime import date
from flask import Blueprint, redirect, request, session
from flask_babel import Babel, format_date

bp = Blueprint('i18n', __name__)


def init_app(app):
    Babel(app, locale_selector=lambda: session.get('language', 'en'))

    @app.template_filter('local_date')
    def local_date(value, pattern='medium'):
        return format_date(date.fromisoformat(value[:10]), format=pattern)

@bp.post('/language')
def change_language():
    session['language'] = request.form.get('language') if request.form.get('language') in ('en', 'bg') else 'en'
    target = request.form.get('next', '/')
    return redirect(target if target.startswith('/') and not target.startswith('//') and '\\' not in target else '/')

