"""Demonstração em loopback e SQLite temporário; nunca lê o banco de produção."""
import hmac
import os
import pathlib
import secrets
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["DATABASE_URL"] = ""
os.environ["RENDER"] = ""
os.environ["DATABASE_PATH"] = str(pathlib.Path(tempfile.mkdtemp(prefix="knn-preview-")) / "preview.db")
os.environ["ADMIN_USERNAME"] = "local-preview"
os.environ["ADMIN_PASSWORD"] = secrets.token_urlsafe(32)
os.environ["SECRET_KEY"] = secrets.token_urlsafe(32)
os.environ["BASE_URL"] = "http://127.0.0.1:5081"

from flask import abort, redirect, request, session, url_for
from inglessecreto import create_app
from inglessecreto.services import experiences as platform

app = create_app()
app.config["PREVIEW_ISOLATED"] = True
admin_token = secrets.token_urlsafe(24)
with platform.connection(write=True) as db:
    camp = platform.campaign(db, "black-friday")
    rev = platform.latest_revision(db, camp["id"])
    for target in platform.TARGETS:
        platform.publish(db, camp["id"], rev["id"], target, True, int(time.time()), None, 10, "local-demo")


@app.route("/__local_preview/<token>")
def enter_preview(token):
    if request.remote_addr != "127.0.0.1" or not hmac.compare_digest(token, admin_token):
        abort(404)
    session["admin_logged"] = True
    return redirect(url_for("studio.dashboard"))


print("LOCAL: http://127.0.0.1:5081/promocoes/black-friday", flush=True)
print("ADMIN: http://127.0.0.1:5081/__local_preview/" + admin_token, flush=True)
app.run(host="127.0.0.1", port=5081, debug=False, use_reloader=False)
