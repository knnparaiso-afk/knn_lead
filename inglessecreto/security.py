"""Rate limit, limites de entrada, cabeçalhos de segurança e hooks globais."""
import hmac
import time

from flask import request, make_response
from flask_wtf.csrf import CSRFError

from config import SECRET_KEY, IS_PRODUCTION
from database import get_connection
from .assets import asset_tem_versao_atual

FIELD_MAX_LENGTHS = {
    "username": 100, "password": 256,
    "nome": 120,
    "whatsapp": 32,
    "email": 254,
    "idade": 3, "frase": 500, "traducao": 1000,
    "opcao_a": 400, "opcao_b": 400, "opcao_c": 400,
    "resposta_correta": 1, "semana": 4,
    "data_inicio": 10, "data_fim": 10,
    "endereco": 250, "parceiro": 150, "descricao": 500,
    "resposta": 500, "codigo": 64,
}

CSP = (
    "default-src 'self'; base-uri 'self'; object-src 'none'; "
    "frame-ancestors 'none'; form-action 'self'; img-src 'self' data: blob:; "
    "font-src 'self' data:; style-src 'self' 'unsafe-inline'; "
    "script-src 'self' 'unsafe-inline'; connect-src 'self' blob: data:"
)


def permitir_requisicao(scope, max_requests, window_seconds):
    """Rate limit persistente no banco, compartilhado por todos os workers."""
    now = int(time.time())
    window_start = (now // window_seconds) * window_seconds
    ip = request.remote_addr or "unknown"
    fingerprint = hmac.new(SECRET_KEY.encode("utf-8"), ip.encode("utf-8"), "sha256").hexdigest()[:24]
    bucket_key = f"{scope}:{fingerprint}:{window_start}"
    connection = get_connection()
    try:
        connection.execute(
            """
            INSERT INTO rate_limit_buckets (bucket_key, window_start, request_count)
            VALUES (?, ?, 1)
            ON CONFLICT(bucket_key) DO UPDATE
              SET request_count = rate_limit_buckets.request_count + 1
            """,
            (bucket_key, window_start),
        )
        row = connection.execute(
            "SELECT request_count FROM rate_limit_buckets WHERE bucket_key = ?",
            (bucket_key,),
        ).fetchone()
        if int(row["request_count"]) == 1:
            connection.execute(
                "DELETE FROM rate_limit_buckets WHERE window_start < ?",
                (now - 172800,),
            )
        connection.commit()
        return int(row["request_count"]) <= max_requests
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def validar_tamanho_de_entrada():
    for field, value in request.form.items():
        if len(value) > FIELD_MAX_LENGTHS.get(field, 2000):
            return make_response("Um dos campos excede o tamanho permitido.", 413)


def adicionar_cabecalhos_de_seguranca(response):
    h = response.headers
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("X-Frame-Options", "DENY")
    h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    h.setdefault("Content-Security-Policy", CSP)
    if request.path.startswith(("/admin", "/participar", "/nada", "/conquista", "/convite/", "/desafio/", "/e/")):
        h["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        h["Pragma"] = "no-cache"
        h.pop("Expires", None)
        if request.path.startswith(("/admin", "/participar", "/nada", "/conquista", "/convite/", "/desafio/")):
            h["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    elif request.path.startswith(("/static/", "/models/")):
        if response.status_code in (200, 304):
            versoes = request.args.getlist("v")
            if (request.path.startswith("/static/") and len(versoes) == 1
                    and asset_tem_versao_atual(request.path, versoes[0])):
                h["Cache-Control"] = "public, max-age=31536000, immutable"
                h.pop("Expires", None)
            else:
                h["Cache-Control"] = "public, max-age=300, must-revalidate"
    elif request.method not in ("GET", "HEAD"):
        h["Cache-Control"] = "no-store"
    elif response.mimetype == "text/html":
        h["Cache-Control"] = "private, no-cache, max-age=0, must-revalidate"
    if IS_PRODUCTION and request.is_secure:
        h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


def csrf_error(_error):
    return (
        "Esta página expirou ou a solicitação não pôde ser validada. "
        "Atualize a página e tente novamente.",
        400,
    )


def register(app):
    app.before_request(validar_tamanho_de_entrada)
    app.after_request(adicionar_cabecalhos_de_seguranca)
    app.register_error_handler(CSRFError, csrf_error)
