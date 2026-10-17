from functools import wraps

from flask import redirect, session, url_for


def admin_required(function):
    @wraps(function)
    def decorated_function(*args, **kwargs):
        if not session.get("admin_logged"):
            return redirect(url_for("auth.admin_login"))
        return function(*args, **kwargs)

    return decorated_function
