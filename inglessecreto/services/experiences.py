"""Sessões, publicações, respostas e funil: regras independentes do motor 3D."""
import json
import re
import secrets
import time
from contextlib import contextmanager
from datetime import datetime

from flask import abort, session

from database import get_connection, PostgreSQLConnection
from ..utils import TZ_BRASIL

CHANNELS = ("direto", "instagram", "whatsapp", "cartaz", "parceiro", "amigo", "outro")
TARGETS = ("promotion", "landing", "game")
EVENTS = {
    "landing_view", "promotion_view", "game_start", "game_complete",
    "result_view", "form_start", "form_complete", "whatsapp_click",
    "friend_share_click", "scheduled", "attended", "enrolled",
}
STATUSES = ("novo", "contatado", "agendado", "compareceu", "faltou", "matriculado", "perdido")


def serialize(content):
    return json.dumps(content, ensure_ascii=False, separators=(",", ":"))


@contextmanager
def connection(write=False):
    db = get_connection()
    try:
        if write and not isinstance(db, PostgreSQLConnection):
            db.execute("BEGIN IMMEDIATE")
        yield db
        if write:
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def campaign(db, slug):
    row = db.execute("SELECT * FROM pl_campaigns WHERE slug = ?", (slug,)).fetchone()
    if not row:
        abort(404)
    return dict(row)


def revision(db, revision_id):
    row = db.execute("SELECT * FROM pl_revisions WHERE id = ?", (revision_id,)).fetchone()
    if not row:
        abort(404)
    item = dict(row)
    item["data"] = json.loads(item["content"])
    return item


def latest_revision(db, campaign_id):
    row = db.execute("SELECT id FROM pl_revisions WHERE campaign_id = ? ORDER BY version DESC LIMIT 1",
                     (campaign_id,)).fetchone()
    return revision(db, row["id"])


def publication(db, campaign_id, target, now=None):
    now = int(time.time()) if now is None else now
    # A scheduled revision does not hide the current one until its start.
    # An ended/disabled latest publication never resurrects an older version.
    row = db.execute(
        "SELECT * FROM pl_publications WHERE campaign_id = ? AND target = ? AND starts_at <= ? "
        "ORDER BY starts_at DESC, id DESC LIMIT 1", (campaign_id, target, now),
    ).fetchone()
    if not row or not row["enabled"] or (row["ends_at"] is not None and row["ends_at"] <= now):
        return None
    item = dict(row)
    item["revision"] = revision(db, row["revision_id"])
    return item


def page_revision(db, campaign_id):
    for target in ("promotion", "landing", "game"):
        pub = publication(db, campaign_id, target)
        if pub:
            return pub["revision"]
    return None


def highlights(db):
    items = []
    for row in db.execute("SELECT * FROM pl_campaigns ORDER BY id").fetchall():
        pub = publication(db, row["id"], "landing")
        if pub:
            items.append(dict(campaign=dict(row), publication=pub, data=pub["revision"]["data"]))
    return sorted(items, key=lambda item: (item["publication"]["priority"], item["publication"]["id"]),
                  reverse=True)[:3]


def visit_id():
    now = int(time.time())
    visit = session.get("pl_visit")
    if not isinstance(visit, dict) or visit.get("until", 0) <= now:
        visit = {"id": secrets.token_hex(12), "until": now + 1800}
        session["pl_visit"] = visit
    return visit["id"]


def capture_source(db, campaign_id, args):
    origins = session.get("pl_origins", {})
    key = str(campaign_id)
    origin = origins.get(key, {"channel": "direto", "batch": ""})
    token = args.get("src", "")
    explicit = False
    if token and len(token) <= 64:
        row = db.execute("SELECT channel,batch FROM pl_sources WHERE campaign_id = ? AND token = ?",
                         (campaign_id, token)).fetchone()
        if row:
            origin, explicit = dict(row), True
    elif args.get("canal") in CHANNELS:
        batch = re.sub(r"[^a-zA-Z0-9_-]", "", args.get("lote", ""))[:40]
        origin = {"channel": args["canal"], "batch": batch}
        explicit = True
    if key not in origins or explicit:
        origins[key] = origin
        session["pl_origins"] = dict(list(origins.items())[-8:])
    return origin


def event(db, key, campaign_id, revision_id, name, origin=None, session_id=None):
    if name not in EVENTS:
        raise ValueError("Evento não permitido.")
    now = int(time.time())
    day = datetime.fromtimestamp(now, TZ_BRASIL).date().isoformat()
    origin = origin or {"channel": "direto", "batch": ""}
    inserted = db.execute(
        "INSERT INTO pl_events (event_key,campaign_id,revision_id,session_id,event,day,channel,batch,created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(event_key) DO NOTHING RETURNING event_key",
        (key, campaign_id, revision_id, session_id, name, day, origin["channel"], origin["batch"], now),
    ).fetchone()
    if inserted:
        db.execute(
            "INSERT INTO pl_daily_metrics (day,campaign_id,revision_id,event,channel,batch,total) "
            "VALUES (?,?,?,?,?,?,1) ON CONFLICT(day,campaign_id,revision_id,event,channel,batch) "
            "DO UPDATE SET total = pl_daily_metrics.total + 1",
            (day, campaign_id, revision_id, name, origin["channel"], origin["batch"]),
        )


def session_event(db, run, name):
    event(db, run["id"] + ":" + name, run["campaign_id"], run["revision_id"], name,
          {"channel": run["channel"], "batch": run["batch"]}, run["id"])


def authorize(db, run_id, lock=False):
    if run_id not in session.get("pl_runs", {}).values():
        abort(404)
    sql = "SELECT * FROM pl_sessions WHERE id = ?"
    if lock and isinstance(db, PostgreSQLConnection):
        sql += " FOR UPDATE"
    row = db.execute(sql, (run_id,)).fetchone()
    if not row:
        abort(404)
    return dict(row)


def start_session(db, camp, rev, origin):
    runs = session.get("pl_runs", {})
    existing = runs.get(camp["slug"])
    if existing:
        row = db.execute("SELECT * FROM pl_sessions WHERE id = ?", (existing,)).fetchone()
        if row:
            benefit = db.execute("SELECT valid_until FROM pl_benefits WHERE session_id=?", (existing,)).fetchone()
            if (not row["completed_at"] and row["expires_at"] > time.time()) or (benefit and benefit["valid_until"] > time.time()):
                return dict(row)
    now = int(time.time())
    run_id = secrets.token_hex(16)
    db.execute(
        "INSERT INTO pl_sessions (id,campaign_id,revision_id,channel,batch,created_at,expires_at) VALUES (?,?,?,?,?,?,?)",
        (run_id, camp["id"], rev["id"], origin["channel"], origin["batch"], now, now + 86400),
    )
    runs[camp["slug"]] = run_id
    session["pl_runs"] = dict(list(runs.items())[-4:])
    run = dict(db.execute("SELECT * FROM pl_sessions WHERE id = ?", (run_id,)).fetchone())
    session_event(db, run, "game_start")
    return run


def public_question(question, position):
    return {key: question[key] for key in ("id", "scene", "skill", "speaker", "title", "prompt", "options", "interaction")} | {"position": position}


def state(db, run):
    content = revision(db, run["revision_id"])["data"]
    count = db.execute("SELECT COUNT(*) AS n FROM pl_answers WHERE session_id = ?", (run["id"],)).fetchone()["n"]
    return {"session_id": run["id"], "completed": bool(run["completed_at"]), "answered": count,
            "total": len(content["questions"]), "revision_id": run["revision_id"],
            "expired": not run["completed_at"] and run["expires_at"] <= time.time(),
            "question": public_question(content["questions"][count], count) if count < len(content["questions"]) else None}


def answer(db, run, position, choice):
    if run["expires_at"] <= time.time():
        abort(410, "Esta sessão expirou. Abra a campanha novamente para começar.")
    content = revision(db, run["revision_id"])["data"]
    questions = content["questions"]
    if type(position) is not int or type(choice) is not int or not 0 <= position < len(questions):
        abort(400, "Resposta inválida.")
    question = questions[position]
    if not 0 <= choice < len(question["options"]):
        abort(400, "Alternativa inválida.")
    previous = db.execute("SELECT answer FROM pl_answers WHERE session_id = ? AND position = ?",
                          (run["id"], position)).fetchone()
    if previous:
        if previous["answer"] != str(choice):
            abort(409, "A primeira resposta deste desafio já foi registrada.")
    else:
        count = db.execute("SELECT COUNT(*) AS n FROM pl_answers WHERE session_id = ?", (run["id"],)).fetchone()["n"]
        if position != count or run["completed_at"]:
            abort(409, "Responda ao desafio atual antes de continuar.")
        now = int(time.time())
        db.execute("INSERT INTO pl_answers (session_id,position,challenge_id,answer,correct,created_at) VALUES (?,?,?,?,?,?)",
                   (run["id"], position, question["id"], str(choice), int(choice == question["correct"]), now))
        if position + 1 == len(questions):
            db.execute("UPDATE pl_sessions SET completed_at = ? WHERE id = ?", (now, run["id"]))
            db.execute("INSERT INTO pl_benefits (session_id,unlocked_at,valid_until) VALUES (?,?,?) ON CONFLICT(session_id) DO NOTHING",
                       (run["id"], now, now + content["offer_days"] * 86400))
            run["completed_at"] = now
            session_event(db, run, "game_complete")
    return {"correct": choice == question["correct"], "explanation": question["explanation"],
            "state": state(db, run)}


def result(db, run):
    if not run["completed_at"]:
        abort(409, "Conclua os sete desafios para continuar.")
    rows = db.execute("SELECT correct FROM pl_answers WHERE session_id = ? ORDER BY position", (run["id"],)).fetchall()
    correct = sum(row["correct"] for row in rows)
    # Descriptive counts only. No unvalidated CEFR or placement thresholds.
    return {"answered": len(rows), "correct": correct,
            "message": "Estas respostas são um ponto de partida para a conversa na sua aula. "
                       "Elas não definem seu nível de inglês e não avaliam fala ou compreensão oral."}


def save_revision(db, campaign_id, content):
    if content.get("module") not in ("daily-adventure@1", "contact-only@1"):
        raise ValueError("Módulo não suportado.")
    if content.get("runtime") != "web@1":
        raise ValueError("Runtime não suportado.")
    if type(content.get("offer_days")) is not int or not 1 <= content["offer_days"] <= 90:
        raise ValueError("O prazo da aula deve ter entre 1 e 90 dias.")
    for key in ("title", "description", "landing_title", "landing_text", "cta", "offer_title", "offer_text", "terms"):
        if not isinstance(content.get(key), str) or not content[key].strip() or len(content[key]) > 1200:
            raise ValueError("Preencha os textos da promoção (até 1.200 caracteres).")
    questions = content.get("questions", [])
    if len(questions) != 7:
        raise ValueError("Esta aventura utiliza exatamente sete desafios.")
    ids = set()
    for question in questions:
        if question.get("id") in ids or not re.fullmatch(r"[a-z0-9_-]{1,40}", question.get("id", "")):
            raise ValueError("Identificador de desafio inválido ou repetido.")
        ids.add(question["id"])
        if question.get("scene") not in ("cafe", "meeting") or question.get("interaction") not in ("character", "objects", "sign", "message"):
            raise ValueError("Cena ou interação não suportada.")
        if question["interaction"] == "objects" and (question["scene"] != "cafe" or question["options"] != ["Apple", "Coffee", "Sandwich"]):
            raise ValueError("A seleção de objetos utiliza Apple, Coffee e Sandwich, nessa ordem.")
        for key in ("skill", "speaker", "title", "prompt", "explanation"):
            if not isinstance(question.get(key), str) or not question[key].strip() or len(question[key]) > 1200:
                raise ValueError("Preencha os textos de todos os desafios.")
        if not isinstance(question.get("options"), list) or len(question["options"]) != 3 or any(not isinstance(o, str) or not o.strip() or len(o) > 400 for o in question["options"]):
            raise ValueError("Cada desafio precisa de três alternativas válidas.")
        if type(question.get("correct")) is not int or not 0 <= question["correct"] < 3:
            raise ValueError("Gabarito inválido.")
    if isinstance(db, PostgreSQLConnection):
        db.execute("SELECT id FROM pl_campaigns WHERE id = ? FOR UPDATE", (campaign_id,))
    row = db.execute("SELECT COALESCE(MAX(version),0) AS v FROM pl_revisions WHERE campaign_id = ?", (campaign_id,)).fetchone()
    return db.execute("INSERT INTO pl_revisions (campaign_id,version,content,created_at) VALUES (?,?,?,?) RETURNING id",
                      (campaign_id, row["v"] + 1, serialize(content), int(time.time()))).fetchone()["id"]


def publish(db, campaign_id, revision_id, target, enabled, starts_at, ends_at, priority, actor):
    rev = revision(db, revision_id)
    if rev["campaign_id"] != campaign_id or target not in TARGETS:
        raise ValueError("Publicação inválida.")
    if target == "game" and enabled and rev["data"]["module"] != "daily-adventure@1":
        raise ValueError("Esta promoção não tem módulo de jogo.")
    if ends_at is not None and ends_at <= starts_at:
        raise ValueError("O término precisa ser posterior ao início.")
    db.execute(
        "INSERT INTO pl_publications (campaign_id,revision_id,target,enabled,starts_at,ends_at,priority,created_at,actor) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (campaign_id, revision_id, target, int(enabled), starts_at, ends_at, priority, int(time.time()), actor),
    )


def commercial_event(db, opportunity, name):
    run = dict(db.execute("SELECT * FROM pl_sessions WHERE id = ?", (opportunity["session_id"],)).fetchone())
    event(db, "opportunity:" + str(opportunity["id"]) + ":" + name,
          run["campaign_id"], run["revision_id"], name,
          {"channel": run["channel"], "batch": run["batch"]}, run["id"])
