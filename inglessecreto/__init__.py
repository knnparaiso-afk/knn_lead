import os
from datetime import timedelta

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from config import SECRET_KEY, IS_PRODUCTION
from database import init_db

from .extensions import csrf
from . import assets, security
from .blueprints import register_blueprints

# templates/ e static/ continuam na raiz do projeto, ao lado do app.py
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def create_app():
    app = Flask(__name__, root_path=ROOT)
    app.secret_key = SECRET_KEY
    app.config.update(
        MAX_CONTENT_LENGTH=64 * 1024,
        SESSION_COOKIE_NAME="__Host-inglessecreto" if IS_PRODUCTION else "inglessecreto_session",
        SESSION_COOKIE_SECURE=IS_PRODUCTION,
        SESSION_COOKIE_PATH="/",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=4),
        SESSION_REFRESH_EACH_REQUEST=False,
        WTF_CSRF_TIME_LIMIT=7200,
        SEND_FILE_MAX_AGE_DEFAULT=300,
    )

    # Render fica atrás de um proxy reverso. Só confiamos um salto e não
    # confiamos X-Forwarded-Host.
    if IS_PRODUCTION:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=0, x_port=0)

    csrf.init_app(app)
    init_db()

    from .platform_schema import init_platform
    from .platform_setup import register_platform
    init_platform()
    register_platform(app)

    assets.register(app)
    security.register(app)
    register_blueprints(app)
    return app
