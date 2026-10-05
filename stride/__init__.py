import os
import secrets
from pathlib import Path
from datetime import date, datetime
from flask import Flask, abort, g, render_template, request, session
from .core import SPORTS
from .database import db, init_app as init_database
from .i18n import init_app as init_i18n


def create_app(test_config=None):
    root = Path(__file__).resolve().parents[1]
    app = Flask(__name__, template_folder=str(root / 'templates'), static_folder=str(root / 'static'), instance_path=str(root / 'instance'))
    app.config.update(SECRET_KEY=os.environ.get('SECRET_KEY'), DATABASE=str(Path(app.instance_path) / 'stride.sqlite'),
                      MAX_CONTENT_LENGTH=64 * 1024, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                      BABEL_TRANSLATION_DIRECTORIES=str(root / 'translations'))
    if test_config:
        app.config.update(test_config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    if not app.config['SECRET_KEY']:
        key_path = Path(app.instance_path) / 'session.key'
        if not key_path.exists():
            key_path.write_text(secrets.token_hex(32))
        app.config['SECRET_KEY'] = key_path.read_text().strip()
    init_i18n(app)
    init_database(app, root / 'schema.sql')

    @app.before_request
    def load_user_and_check_csrf():
        g.user = db().execute('SELECT * FROM users WHERE id = ?', (session.get('user_id'),)).fetchone()
        session.setdefault('csrf', secrets.token_hex(32))
        if request.method == 'POST' and not secrets.compare_digest(session['csrf'], request.form.get('csrf', '')):
            abort(400)

    @app.context_processor
    def common():
        return dict(sports=SPORTS, today=date.today().isoformat(), language=session.get('language', 'en'),
                    csrf=session['csrf'], now=datetime.now().strftime('%Y-%m-%dT%H:%M'))

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def error_page(error):
        return render_template('error.html', error=error), error.code

    from . import accounts, workouts, groups, events, dashboard, i18n, training
    for module in (accounts, workouts, groups, events, dashboard, i18n, training):
        app.register_blueprint(module.bp)
    return app
