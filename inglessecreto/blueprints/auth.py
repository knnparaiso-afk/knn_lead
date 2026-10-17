import hmac

from flask import (Blueprint, flash, make_response, redirect,
                   render_template, request, session, url_for)

from config import ADMIN_USERNAME, ADMIN_PASSWORD
from ..security import permitir_requisicao

bp = Blueprint("auth", __name__)


@bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST" and not permitir_requisicao("admin_login", 8, 900):
        flash("Muitas tentativas de acesso. Aguarde 15 minutos e tente novamente.", "error")
        return make_response(render_template("admin/login.html"), 429)

    if session.get("admin_logged"):
        return redirect(url_for("reports.admin_dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        senha_correta = False
        if ADMIN_PASSWORD.startswith(("pbkdf2:", "scrypt:", "argon2:")):
            from werkzeug.security import check_password_hash
            senha_correta = check_password_hash(ADMIN_PASSWORD, password)
        else:
            senha_correta = hmac.compare_digest(password, ADMIN_PASSWORD)

        if hmac.compare_digest(username, ADMIN_USERNAME) and senha_correta:
            session.clear()  # rotaciona a sessão para reduzir fixation
            session.permanent = True
            session["admin_logged"] = True
            return redirect(url_for("reports.admin_dashboard"))

        flash("Usuário ou senha incorretos.", "error")

    return render_template("admin/login.html")


@bp.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.clear()
    return redirect(url_for("auth.admin_login"))
