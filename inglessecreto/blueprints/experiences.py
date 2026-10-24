"""Experiências sem dependência de QR/local, com cadastro compartilhado."""
import secrets
import mimetypes
from pathlib import Path
import time
from urllib.parse import urlencode

from flask import (Blueprint, abort, flash, jsonify, make_response, redirect,
                   render_template, request, session, url_for, current_app, send_from_directory)
from werkzeug.exceptions import HTTPException

from config import BASE_URL, UNIDADE
from telefones import normalizar_whatsapp
from ..security import permitir_requisicao
from ..services import experiences as platform
from ..services.participants import (
    gerar_token_participante, obter_id_por_token, validar_formulario,
    _bloquear_gravacao, _ids_por_whatsapp, registrar_consentimento,
    PARTICIPATION_CONSENT_TEXT, GUARDIAN_CONSENT_TEXT,
)

bp = Blueprint("experiences", __name__)


@bp.route("/static/experiences/<path:filename>")
def experience_asset(filename):
    directory = Path(current_app.static_folder) / "experiences"
    compressed = (directory / (filename + ".gz")).resolve()
    if directory.resolve() in compressed.parents and compressed.is_file() and request.accept_encodings["gzip"] > 0:
        response = send_from_directory(directory, filename + ".gz",
                                       mimetype=mimetypes.guess_type(filename)[0] or "application/octet-stream")
        response.headers["Content-Encoding"] = "gzip"
    else:
        response = send_from_directory(directory, filename)
    response.vary.add("Accept-Encoding")
    return response


@bp.errorhandler(HTTPException)
def experience_error(error):
    if request.path.startswith("/api/experiencias/"):
        return jsonify(message=error.description), error.code
    return error


@bp.route("/experiencias/creditos")
def credits():
    return render_template("experiences/credits.html", content={"title": "Créditos"})


@bp.route("/privacidade")
def privacy():
    from config import PRIVACY_CONTROLLER_NAME, PRIVACY_CONTROLLER_CNPJ, PRIVACY_CONTACT_EMAIL
    return render_template("experiences/privacy.html", content={"title": "Privacidade"},
                           controller=PRIVACY_CONTROLLER_NAME, cnpj=PRIVACY_CONTROLLER_CNPJ,
                           contact=PRIVACY_CONTACT_EMAIL)


def _recognized(db):
    user_id = obter_id_por_token(request.cookies.get("knn_lead_token"))
    if user_id:
        return db.execute("SELECT id,nome,whatsapp,email,idade FROM usuarios WHERE id = ?", (user_id,)).fetchone()
    return None


@bp.route("/promocoes/<slug>")
def promotion(slug):
    with platform.connection(write=True) as db:
        camp = platform.campaign(db, slug)
        rev = platform.page_revision(db, camp["id"])
        if not rev:
            abort(404)
        origin = platform.capture_source(db, camp["id"], request.args)
        platform.event(db, platform.visit_id() + ":" + str(camp["id"]) + ":promotion_view",
                       camp["id"], rev["id"], "promotion_view", origin)
        game = platform.publication(db, camp["id"], "game")
        legacy_available = False
        if rev["data"]["module"] == "contact-only@1":
            from ..services.campaigns import filtro_campanha_vigente, parametros_vigencia
            legacy_available = db.execute(
                "SELECT id FROM campanhas WHERE " + filtro_campanha_vigente() + " LIMIT 1",
                parametros_vigencia(),
            ).fetchone() is not None
    return render_template("experiences/promotion.html", campaign=camp, content=rev["data"],
                           playable=bool(game), legacy_available=legacy_available, u=UNIDADE)


@bp.route("/r/<token>")
def source_link(token):
    with platform.connection() as db:
        row = db.execute("SELECT c.slug FROM pl_sources s JOIN pl_campaigns c ON c.id = s.campaign_id WHERE s.token = ?",
                         (token,)).fetchone()
        if not row:
            abort(404)
    return redirect(url_for("experiences.promotion", slug=row["slug"], src=token), 302)


@bp.route("/jogar/<slug>/iniciar", methods=["POST"])
def start(slug):
    if not permitir_requisicao("experience_start", 120, 600):
        abort(429)
    with platform.connection(write=True) as db:
        camp = platform.campaign(db, slug)
        pub = platform.publication(db, camp["id"], "game")
        if not pub:
            flash("O jogo está pausado. Você pode falar com a KNN para combinar sua aula.", "info")
            return redirect(url_for("experiences.promotion", slug=slug))
        origin = platform.capture_source(db, camp["id"], request.args)
        run = platform.start_session(db, camp, pub["revision"], origin)
    return redirect(url_for("experiences.play", run_id=run["id"]))


@bp.route("/experiencia/<run_id>")
def play(run_id):
    with platform.connection() as db:
        run = platform.authorize(db, run_id)
        if run["completed_at"]:
            return redirect(url_for("experiences.finish", run_id=run_id))
        rev = platform.revision(db, run["revision_id"])
    return render_template("experiences/play.html", content=rev["data"], preview=False,
                           experience_config={"sessionId": run_id, "preview": False,
                                   "stateUrl": url_for("experiences.get_state", run_id=run_id),
                                   "answerUrl": url_for("experiences.submit_answer", run_id=run_id),
                                   "resultUrl": url_for("experiences.finish", run_id=run_id)})


@bp.route("/api/experiencias/<run_id>")
def get_state(run_id):
    with platform.connection() as db:
        return jsonify(platform.state(db, platform.authorize(db, run_id)))


@bp.route("/api/experiencias/<run_id>/respostas", methods=["POST"])
def submit_answer(run_id):
    if not permitir_requisicao("experience_answer", 600, 300):
        abort(429)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400)
    with platform.connection(write=True) as db:
        run = platform.authorize(db, run_id, lock=True)
        return jsonify(platform.answer(db, run, data.get("position"), data.get("choice")))


@bp.route("/experiencia/<run_id>/resultado")
def finish(run_id):
    with platform.connection(write=True) as db:
        run = platform.authorize(db, run_id)
        outcome = platform.result(db, run)
        rev = platform.revision(db, run["revision_id"])
        platform.session_event(db, run, "result_view")
        opportunity = db.execute("SELECT reference FROM pl_opportunities WHERE campaign_id = ? AND participant_id = ?",
                                 (run["campaign_id"], run["participant_id"])).fetchone()
        benefit = db.execute("SELECT valid_until FROM pl_benefits WHERE session_id = ?", (run_id,)).fetchone()
    return render_template("experiences/result.html", run=run, content=rev["data"],
                           outcome=outcome, opportunity=opportunity, benefit=benefit,
                           offer_expired=benefit["valid_until"] <= time.time(), u=UNIDADE)


@bp.route("/experiencia/<run_id>/cadastro", methods=["GET", "POST"])
def register(run_id):
    if request.method == "POST" and not permitir_requisicao("experience_register", 60, 600):
        abort(429)
    with platform.connection(write=True) as db:
        run = platform.authorize(db, run_id, lock=request.method == "POST")
        platform.result(db, run)
        content = platform.revision(db, run["revision_id"])["data"]
        benefit = db.execute("SELECT * FROM pl_benefits WHERE session_id = ?", (run_id,)).fetchone()
        if not benefit or benefit["valid_until"] <= time.time():
            flash("O prazo desta oferta terminou. Fale com a KNN para conhecer as oportunidades atuais.", "info")
            return redirect(url_for("experiences.finish", run_id=run_id))
        person = _recognized(db)
        if request.method == "GET":
            platform.session_event(db, run, "form_start")
            return render_template("experiences/register.html", run=run, content=content, participante=person)
        if request.form.get("confirmar_reconhecido") == "1" and person:
            name, phone, email, age = person["nome"], person["whatsapp"], person["email"], person["idade"]
        else:
            name = request.form.get("nome", "").strip()
            phone = request.form.get("whatsapp", "").strip()
            email = request.form.get("email", "").strip()
            age = request.form.get("idade", "").strip()
            if not all((name, phone, email, age, request.form.get("participacao_confirmada"))):
                flash("Preencha os campos e confirme sua participação.", "error")
                return render_template("experiences/register.html", run=run, content=content, participante=person), 400
        age, error = validar_formulario(name, phone, email, age)
        if error:
            flash(error, "error")
            return render_template("experiences/register.html", run=run, content=content, participante=person), 400
        # Same identity and validation rules as the existing participant flow.
        # No discovery, fake QR, or ENGLISH_PASS_REQUIRED is created here.
        _bloquear_gravacao(db)
        phone = normalizar_whatsapp(phone)
        ids = _ids_por_whatsapp(db, phone)
        if ids:
            participant_id = ids[0]
            db.execute("UPDATE usuarios SET nome=?,whatsapp=?,email=?,idade=? WHERE id=?",
                       (name, phone, email, age, participant_id))
        else:
            participant_id = db.execute(
                "INSERT INTO usuarios (nome,whatsapp,email,idade) VALUES (?,?,?,?) RETURNING id",
                (name, phone, email, age),
            ).fetchone()["id"]
        existing = db.execute("SELECT * FROM pl_opportunities WHERE campaign_id=? AND participant_id=?",
                              (run["campaign_id"], participant_id)).fetchone()
        if not existing:
            registrar_consentimento(db, participant_id, "participacao_e_mensagens", PARTICIPATION_CONSENT_TEXT)
            if age < 18:
                registrar_consentimento(db, participant_id, "responsavel_legal", GUARDIAN_CONSENT_TEXT)
            now = int(time.time())
            db.execute(
                "INSERT INTO pl_opportunities (reference,campaign_id,participant_id,session_id,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?) ON CONFLICT(campaign_id,participant_id) DO NOTHING",
                (secrets.token_hex(5).upper(), run["campaign_id"], participant_id, run_id, now, now),
            )
        db.execute("UPDATE pl_sessions SET participant_id=? WHERE id=?", (participant_id, run_id))
        # One lead per participant/campaign; network retries don't inflate the funnel.
        opportunity = db.execute("SELECT * FROM pl_opportunities WHERE campaign_id=? AND participant_id=?",
                                 (run["campaign_id"], participant_id)).fetchone()
        platform.commercial_event(db, opportunity, "form_complete")
    response = make_response(redirect(url_for("experiences.finish", run_id=run_id)))
    response.set_cookie("knn_lead_token", gerar_token_participante(participant_id),
                        max_age=86400 * 365, httponly=True, samesite="Lax", secure=request.is_secure)
    return response


@bp.route("/experiencia/<run_id>/outra-pessoa", methods=["POST"])
def reset_participant(run_id):
    with platform.connection() as db:
        platform.authorize(db, run_id)
    response = make_response(redirect(url_for("experiences.register", run_id=run_id)))
    response.delete_cookie("knn_lead_token")
    return response


@bp.route("/experiencia/<run_id>/whatsapp", methods=["POST"])
def whatsapp(run_id):
    with platform.connection(write=True) as db:
        run = platform.authorize(db, run_id)
        platform.result(db, run)
        opportunity = db.execute("SELECT reference FROM pl_opportunities WHERE campaign_id=? AND participant_id=?",
                                 (run["campaign_id"], run["participant_id"])).fetchone()
        if not opportunity:
            return redirect(url_for("experiences.register", run_id=run_id))
        platform.session_event(db, run, "whatsapp_click")
    text = "Olá! Concluí o Inglês Secreto e quero combinar minha aula grátis. Referência: " + opportunity["reference"]
    phone = re_phone(UNIDADE["whatsapp"])
    return redirect("https://wa.me/" + phone + "?" + urlencode({"text": text}), 303)


def re_phone(value):
    return "".join(c for c in value if c.isdigit())


@bp.route("/experiencia/<run_id>/convidar", methods=["POST"])
def invite(run_id):
    with platform.connection(write=True) as db:
        run = platform.authorize(db, run_id)
        platform.result(db, run)
        platform.session_event(db, run, "friend_share_click")
        slug = db.execute("SELECT slug FROM pl_campaigns WHERE id=?", (run["campaign_id"],)).fetchone()["slug"]
    link = BASE_URL + url_for("experiences.promotion", slug=slug, canal="amigo", lote="convites")
    return redirect("https://wa.me/?" + urlencode({"text": "Experimente um dia em inglês com a KNN: " + link}), 303)
