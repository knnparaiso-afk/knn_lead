from .public import bp as public_bp
from .models import bp as models_bp
from .auth import bp as auth_bp
from .reports import bp as reports_bp
from .campaigns import bp as campaigns_bp
from .locations import bp as locations_bp
from .qr import bp as qr_bp
from .partner_qr import bp as partner_qr_bp


def register_blueprints(app):
    for bp in (public_bp, models_bp, auth_bp, reports_bp,
               campaigns_bp, locations_bp, qr_bp, partner_qr_bp):
        app.register_blueprint(bp)
