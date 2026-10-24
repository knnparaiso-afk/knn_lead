"""Estúdio específico da aventura: rascunhos, publicações e atendimento."""
import copy
import io
import re
import secrets
import time
from datetime import datetime

import qrcode
from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for

from config import ADMIN_USERNAME, BASE_URL
from ..decorators import admin_required
from ..services import experiences as platform
from ..services.experience_content import initial_content
from ..utils import TZ_BRASIL

bp = Blueprint("studio", __name__, url_prefix="/admin/estudio")


def local_timestamp(value):
    if not value:
        return None
    try:
        return int(datetime.fromisoformat(value).replace(tzinfo=TZ_BRASIL).timestamp())
    except (ValueError, OverflowError):
        raise ValueError("Informe uma data e horário válidos.")


@bp.route("")
@admin_required
def dashboard():
    with platform.connection() as db:
        campaigns = []
        for row in db.execute("SELECT * FROM pl_campaigns ORDER BY id DESC").fetchall():
            item = dict(row)
            item["revision"] = platform.latest_revision(db, row["id"])
            item["publications"] = {target: platform.publication(db, row["id"], target) for target in platform.TARGETS}
            campaigns.append(item)
    return render_template("studio/dashboard.html", campaigns=campaigns)


@bp.route("/nova", methods=["POST"])
@admin_required
def create():
    name = request.form.get("name", "").strip()
    slug = request.form.get("slug", "").strip()
    if not name or len(name) > 120 or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug) or len(slug) > 60:
        flash("Informe nome e endereço válidos (letras minúsculas, números e hífen).", "error")
        return redirect(url_for("studio.dashboard"))
    with platform.connection(write=True) as db:
        if db.execute("SELECT id FROM pl_campaigns WHERE slug=?", (slug,)).fetchone():
            flash("Este endereço já está em uso.", "error")
            return redirect(url_for("studio.dashboard"))
        campaign_id = db.execute("INSERT INTO pl_campaigns (slug,name,created_at) VALUES (?,?,?) RETURNING id",
                                 (slug, name, int(time.time()))).fetchone()["id"]
        platform.save_revision(db, campaign_id, initial_content())
    return redirect(url_for("studio.edit", campaign_id=campaign_id))


@bp.route("/<int:campaign_id>", methods=["GET", "POST"])
@admin_required
def edit(campaign_id):
    with platform.connection(write=request.method == "POST") as db:
        row = db.execute("SELECT * FROM pl_campaigns WHERE id=?", (campaign_id,)).fetchone()
        if not row:
            abort(404)
        rev = platform.latest_revision(db, campaign_id)
        if request.method == "POST":
            data = copy.deepcopy(rev["data"])
            for key in ("title", "description", "landing_title", "landing_text", "cta", "offer_title", "offer_text", "terms"):
                data[key] = request.form.get(key, "").strip()
            try:
                data["offer_days"] = int(request.form.get("offer_days", ""))
                for i, question in enumerate(data["questions"]):
                    for key in ("title", "prompt", "explanation"):
                        question[key] = request.form.get("q" + str(i) + "_" + key, "").strip()
                    question["options"] = [request.form.get("q" + str(i) + "_option" + str(j), "").strip() for j in range(3)]
                    question["correct"] = int(request.form.get("q" + str(i) + "_correct", ""))
                platform.save_revision(db, campaign_id, data)
                flash("Nova revisão salva como rascunho. Nenhuma publicação foi alterada.", "success")
                return redirect(url_for("studio.edit", campaign_id=campaign_id))
            except ValueError as error:
                flash(str(error), "error")
                rev["data"] = data
        revisions = db.execute("SELECT id,version,created_at FROM pl_revisions WHERE campaign_id=? ORDER BY version DESC",
                               (campaign_id,)).fetchall()
        publications = db.execute(
            "SELECT p.*,r.version FROM pl_publications p JOIN pl_revisions r ON r.id=p.revision_id "
            "WHERE p.campaign_id=? ORDER BY p.id DESC LIMIT 40", (campaign_id,),
        ).fetchall()
        sources = db.execute("SELECT * FROM pl_sources WHERE campaign_id=? ORDER BY id DESC", (campaign_id,)).fetchall()
    return render_template("studio/edit.html", campaign=row, revision=rev, revisions=revisions,
                           publications=publications, sources=sources, channels=platform.CHANNELS, base_url=BASE_URL)


@bp.route("/<int:campaign_id>/publicar", methods=["POST"])
@admin_required
def publish(campaign_id):
    try:
        revision_id = int(request.form.get("revision_id", ""))
        starts = local_timestamp(request.form.get("starts_at")) or int(time.time())
        ends = local_timestamp(request.form.get("ends_at"))
        priority = int(request.form.get("priority", "0"))
        if not -999 <= priority <= 999:
            raise ValueError("Prioridade fora do intervalo.")
        with platform.connection(write=True) as db:
            platform.publish(db, campaign_id, revision_id, request.form.get("target"),
                             request.form.get("enabled") == "1", starts, ends, priority, ADMIN_USERNAME)
        flash("Publicação registrada. Os outros canais e as sessões existentes foram preservados.", "success")
    except ValueError as error:
        flash(str(error), "error")
    return redirect(url_for("studio.edit", campaign_id=campaign_id))


@bp.route("/previa/<int:revision_id>")
@admin_required
def preview(revision_id):
    with platform.connection() as db:
        rev = platform.revision(db, revision_id)
    return render_template("experiences/play.html", content=rev["data"], preview=True,
                           experience_config={"preview": True, "questions": rev["data"]["questions"],
                                   "revisionId": rev["id"], "resultUrl": ""})


@bp.route("/<int:campaign_id>/origens", methods=["POST"])
@admin_required
def source(campaign_id):
    channel = request.form.get("channel")
    batch = request.form.get("batch", "").strip()
    if channel not in platform.CHANNELS or not re.fullmatch(r"[a-zA-Z0-9_-]{1,40}", batch):
        flash("Escolha um canal e um lote com até 40 letras, números ou hífens.", "error")
        return redirect(url_for("studio.edit", campaign_id=campaign_id))
    with platform.connection(write=True) as db:
        if not db.execute("SELECT id FROM pl_campaigns WHERE id=?", (campaign_id,)).fetchone():
            abort(404)
        db.execute("INSERT INTO pl_sources (token,campaign_id,channel,batch,created_at) VALUES (?,?,?,?,?)",
                   (secrets.token_urlsafe(9), campaign_id, channel, batch, int(time.time())))
    return redirect(url_for("studio.edit", campaign_id=campaign_id))


@bp.route("/origens/<int:source_id>/qr.png")
@admin_required
def qr(source_id):
    with platform.connection() as db:
        item = db.execute("SELECT token FROM pl_sources WHERE id=?", (source_id,)).fetchone()
        if not item:
            abort(404)
    output = io.BytesIO()
    qrcode.make(BASE_URL + url_for("experiences.source_link", token=item["token"])).save(output, format="PNG")
    output.seek(0)
    return send_file(output, mimetype="image/png", as_attachment=True, download_name="qr-" + item["token"] + ".png")


@bp.route("/atendimento")
@admin_required
def leads():
    status = request.args.get("status", "")
    page = max(1, min(request.args.get("page", 1, type=int), 10000))
    with platform.connection() as db:
        args = []
        where = ""
        if status in platform.STATUSES:
            where = " WHERE o.status=?"
            args.append(status)
        rows = db.execute(
            "SELECT o.*,u.nome,u.whatsapp,u.email,u.idade,c.name AS campaign_name "
            "FROM pl_opportunities o JOIN usuarios u ON u.id=o.participant_id "
            "JOIN pl_campaigns c ON c.id=o.campaign_id" + where +
            " ORDER BY o.updated_at DESC,o.id DESC LIMIT 51 OFFSET ?", (*args, (page - 1) * 50),
        ).fetchall()
    return render_template("studio/leads.html", leads=rows[:50], has_next=len(rows) > 50,
                           page=page, status=status, statuses=platform.STATUSES)


@bp.route("/atendimento/<int:opportunity_id>", methods=["GET", "POST"])
@admin_required
def lead(opportunity_id):
    with platform.connection(write=request.method == "POST") as db:
        sql = "SELECT * FROM pl_opportunities WHERE id=?"
        if request.method == "POST" and isinstance(db, platform.PostgreSQLConnection):
            sql += " FOR UPDATE"
        item = db.execute(sql, (opportunity_id,)).fetchone()
        if not item:
            abort(404)
        item = dict(item)
        if request.method == "POST":
            status = request.form.get("status")
            owner = request.form.get("owner", "").strip()
            next_action = request.form.get("next_action", "").strip()
            note = request.form.get("note", "").strip()
            try:
                if status not in platform.STATUSES or len(owner) > 100 or len(next_action) > 300 or len(note) > 1000:
                    raise ValueError("Revise os dados de atendimento.")
                starts_at = local_timestamp(request.form.get("appointment_at"))
                appointment_id = request.form.get("appointment_id", type=int)
                now = int(time.time())
                if starts_at:
                    db.execute("INSERT INTO pl_appointments (opportunity_id,starts_at,created_at) VALUES (?,?,?)",
                               (opportunity_id, starts_at, now))
                    platform.commercial_event(db, item, "scheduled")
                    status = "agendado"
                elif status in ("compareceu", "faltou"):
                    appointment = db.execute("SELECT * FROM pl_appointments WHERE id=? AND opportunity_id=?",
                                              (appointment_id, opportunity_id)).fetchone()
                    if not appointment:
                        raise ValueError("Selecione o agendamento ao registrar presença ou falta.")
                    db.execute("UPDATE pl_appointments SET status=? WHERE id=?", (status, appointment_id))
                    if status == "compareceu":
                        platform.commercial_event(db, item, "attended")
                elif status == "agendado" and item["status"] != "agendado":
                    raise ValueError("Informe a data do agendamento confirmado.")
                if status == "matriculado":
                    platform.commercial_event(db, item, "enrolled")
                db.execute("UPDATE pl_opportunities SET status=?,owner=?,next_action=?,updated_at=? WHERE id=?",
                           (status, owner, next_action, now, opportunity_id))
                db.execute("INSERT INTO pl_commercial_history (opportunity_id,status,note,actor,created_at) VALUES (?,?,?,?,?)",
                           (opportunity_id, status, note, ADMIN_USERNAME, now))
                flash("Atendimento atualizado.", "success")
                return redirect(url_for("studio.lead", opportunity_id=opportunity_id))
            except ValueError as error:
                flash(str(error), "error")
        person = db.execute("SELECT * FROM usuarios WHERE id=?", (item["participant_id"],)).fetchone()
        run = dict(db.execute("SELECT * FROM pl_sessions WHERE id=?", (item["session_id"],)).fetchone())
        outcome = platform.result(db, run)
        answers = db.execute("SELECT position,correct FROM pl_answers WHERE session_id=? ORDER BY position", (run["id"],)).fetchall()
        questions = platform.revision(db, run["revision_id"])["data"]["questions"]
        history = db.execute("SELECT * FROM pl_commercial_history WHERE opportunity_id=? ORDER BY id DESC LIMIT 50",
                             (opportunity_id,)).fetchall()
        appointments = db.execute("SELECT * FROM pl_appointments WHERE opportunity_id=? ORDER BY id DESC", (opportunity_id,)).fetchall()
    return render_template("studio/lead.html", lead=item, person=person, run=run, outcome=outcome,
                           answers=answers, questions=questions, history=history,
                           appointments=appointments, statuses=platform.STATUSES)


@bp.route("/metricas")
@admin_required
def metrics():
    start = request.args.get("start", "")
    end = request.args.get("end", "")
    filters, args = [], []
    for value, operator in ((start, ">="), (end, "<=")):
        if value:
            try:
                datetime.strptime(value, "%Y-%m-%d")
                filters.append("m.day " + operator + " ?")
                args.append(value)
            except ValueError:
                abort(400)
    where = " WHERE " + " AND ".join(filters) if filters else ""
    with platform.connection() as db:
        rows = db.execute(
            "SELECT c.name,r.version,m.event,m.channel,m.batch,SUM(m.total) AS total "
            "FROM pl_daily_metrics m JOIN pl_campaigns c ON c.id=m.campaign_id JOIN pl_revisions r ON r.id=m.revision_id" +
            where + " GROUP BY c.name,r.version,m.event,m.channel,m.batch ORDER BY c.name,r.version,m.event LIMIT 1000", args,
        ).fetchall()
    return render_template("studio/metrics.html", rows=rows, start=start, end=end)
