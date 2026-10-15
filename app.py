from functools import wraps
from datetime import datetime, timedelta
import os
import secrets
import hmac
import string
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import qrcode
from PIL import Image, ImageDraw, ImageFont

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    send_file,
    send_from_directory,
    jsonify,
    make_response
)

from config import (
    SECRET_KEY,
    ADMIN_USERNAME,
    ADMIN_PASSWORD,
    BASE_URL,
    ENGLISH_PASS_REQUIRED,
    IS_PRODUCTION,
    PRIVACY_CONTROLLER_NAME,
    PRIVACY_CONTROLLER_CNPJ,
    PRIVACY_CONTACT_EMAIL
)

from database import get_connection, init_db
from desafios import CATEGORIAS, DESAFIOS, sortear_desafio, obter_desafio_por_id
from flask_wtf.csrf import CSRFProtect, CSRFError
from werkzeug.middleware.proxy_fix import ProxyFix


app = Flask(__name__)
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
)


hoje = datetime.now(ZoneInfo("America/Sao_Paulo")).date()

# Render fica atrás de um proxy reverso. Só confiamos um salto e não confiamos
# X-Forwarded-Host, para não aceitar hostnames arbitrários nas URLs geradas.
if IS_PRODUCTION:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=0, x_port=0)

csrf = CSRFProtect(app)

init_db()

PRIVACY_NOTICE_VERSION = "2026-10-13-v1"
CONSENT_TEXT_VERSION = "2026-10-13-v3"
PARTICIPATION_CONSENT_TEXT = (
    "Concordo em participar da campanha e autorizo a unidade KNN responsável "
    "a entrar em contato comigo por WhatsApp ou e-mail, inclusive para enviar mensagens "
    "sobre a campanha, novidades, promoções e oportunidades relacionadas aos cursos da unidade. "
    "Se a pessoa participante tiver menos de 18 anos, declaro ser pai, mãe ou responsável legal "
    "e autorizo sua participação e esses contatos."
)
GUARDIAN_CONSENT_TEXT = (
    "Declaro ser pai, mãe ou responsável legal pela pessoa menor de 18 anos e "
    "autorizo sua participação na campanha e o contato por WhatsApp ou e-mail, "
    "incluindo mensagens relacionadas, novidades, promoções e oportunidades da unidade."
)

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


def registrar_consentimento(connection, usuario_id, tipo, texto, versao=None):
    """Grava a versão e o texto exato da declaração afirmada no formulário."""
    connection.execute(
        """
        INSERT INTO registros_consentimento (usuario_id, tipo, versao, texto)
        VALUES (?, ?, ?, ?)
        """,
        (usuario_id, tipo, versao or CONSENT_TEXT_VERSION, texto),
    )


def permitir_requisicao(scope, max_requests, window_seconds):
    """Rate limit persistente no banco, compartilhado por todos os workers."""
    now = int(time.time())
    window_start = (now // window_seconds) * window_seconds
    ip = request.remote_addr or "unknown"
    # Pseudonimiza o IP para não manter o endereço em texto simples na tabela.
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
        # Limpeza ocasional dos buckets antigos para a tabela não crescer sem limite.
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


@app.before_request
def validar_tamanho_de_entrada():
    # MAX_CONTENT_LENGTH limita o tamanho total; estes limites são por campo.
    for field, value in request.form.items():
        limit = FIELD_MAX_LENGTHS.get(field, 2000)
        if len(value) > limit:
            return make_response("Um dos campos excede o tamanho permitido.", 413)


@app.after_request
def adicionar_cabecalhos_de_seguranca(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; base-uri 'self'; object-src 'none'; "
        "frame-ancestors 'none'; form-action 'self'; img-src 'self' data: blob:; "
        "font-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; connect-src 'self' blob: data:",
    )
    if request.path.startswith(("/admin", "/participar", "/nada")):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    if IS_PRODUCTION and request.is_secure:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    return response


@app.route("/models/<path:filename>")
def servir_modelos(filename):
    """Serve modelos 3D da pasta models com cache e MIME type apropriado."""
    return send_from_directory("models", filename)


@app.errorhandler(CSRFError)
def csrf_error(_error):
    return (
        "Esta página expirou ou a solicitação não pôde ser validada. "
        "Atualize a página e tente novamente.",
        400,
    )


@app.before_request
def desativar_campanhas_expiradas():
    """Desativa automaticamente campanhas cuja data_fim já passou."""
    hoje = datetime.now().strftime("%Y-%m-%d")
    connection = get_connection()
    connection.execute(
        """
        UPDATE campanhas
        SET ativa = 0
        WHERE ativa = 1
          AND data_fim IS NOT NULL
          AND TRIM(data_fim) != ''
          AND data_fim < ?
        """,
        (hoje,)
    )
    connection.commit()
    connection.close()


# =========================================================
# UTILITÁRIOS
# =========================================================

def gerar_codigo(tamanho=12):
    caracteres = string.ascii_uppercase + string.digits

    while True:
        codigo = "".join(
            secrets.choice(caracteres)
            for _ in range(tamanho)
        )

        connection = get_connection()

        existe_campanha = connection.execute(
            "SELECT id FROM campanhas WHERE codigo = ?",
            (codigo,)
        ).fetchone()

        existe_qr = connection.execute(
            "SELECT id FROM qr_codes WHERE codigo = ?",
            (codigo,)
        ).fetchone()

        connection.close()

        if not existe_campanha and not existe_qr:
            return codigo


def usuario_tem_pass(usuario_id):
    connection = get_connection()

    quantidade = connection.execute(
        """
        SELECT COUNT(*) AS total
        FROM descobertas
        WHERE usuario_id = ?
        """,
        (usuario_id,)
    ).fetchone()["total"]

    connection.close()

    return quantidade >= ENGLISH_PASS_REQUIRED


def quantidade_descobertas(usuario_id):
    connection = get_connection()

    quantidade = connection.execute(
        """
        SELECT COUNT(*) AS total
        FROM descobertas
        WHERE usuario_id = ?
        """,
        (usuario_id,)
    ).fetchone()["total"]

    connection.close()

    return quantidade


def normalizar_resposta(valor):
    """Compara respostas sem diferenciar maiúsculas, acentos ou pontuação."""
    import re
    import unicodedata

    texto = unicodedata.normalize("NFD", valor.lower())
    texto = "".join(caractere for caractere in texto if not unicodedata.combining(caractere))
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()


def criar_pass_se_necessario(usuario_id):
    if not usuario_tem_pass(usuario_id):
        return

    connection = get_connection()

    existe = connection.execute(
        """
        SELECT id
        FROM premios
        WHERE usuario_id = ?
        """,
        (usuario_id,)
    ).fetchone()

    if not existe:
        recompensa = connection.execute(
            """
            SELECT id
            FROM recompensas
            WHERE ativa = 1
            ORDER BY id
            LIMIT 1
            """
        ).fetchone()

        if recompensa:
            connection.execute(
                """
                INSERT INTO premios
                (usuario_id, recompensa_id)
                VALUES (?, ?)
                """,
                (
                    usuario_id,
                    recompensa["id"]
                )
            )

    connection.commit()
    connection.close()


def admin_required(function):
    @wraps(function)
    def decorated_function(*args, **kwargs):

        if not session.get("admin_logged"):
            return redirect(
                url_for("admin_login")
            )

        return function(*args, **kwargs)

    return decorated_function


# =========================================================
# PÚBLICO
# =========================================================

@app.route("/")
def index():

    connection = get_connection()

    campanha = connection.execute(
        """
        SELECT *
        FROM campanhas
        WHERE ativa = 1
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()

    connection.close()

    return render_template(
        "index.html",
        campanha=campanha
    )


@app.route("/e/<codigo>")
def mensagem(codigo):

    connection = get_connection()

    qr = connection.execute(
        """
        SELECT
            qr_codes.*,
            campanhas.nome AS campanha_nome,
            campanhas.semana,
            campanhas.categoria,
            campanhas.ativa,
            campanhas.data_inicio,
            campanhas.data_fim,
            locais.nome AS local_nome,
            locais.parceiro
        FROM qr_codes
        INNER JOIN campanhas
            ON campanhas.id = qr_codes.campanha_id
        LEFT JOIN locais
            ON locais.id = qr_codes.local_id
        WHERE qr_codes.codigo = ?
          AND (
              qr_codes.local_id IS NULL
              OR locais.ativo = 1
          )
        """,
        (codigo,)
    ).fetchone()

    connection.close()

    # QR Code inexistente ou local inativo
    if not qr:
        return render_template(
            "mensagem.html",
            erro="Mensagem não encontrada."
        ), 404

    # Data atual no horário de Brasília
    hoje = datetime.now().date()

    # Converte as datas do banco
    data_inicio = (
        datetime.strptime(
            qr["data_inicio"], "%Y-%m-%d"
        ).date()
        if qr["data_inicio"] else None
    )

    data_fim = (
        datetime.strptime(
            qr["data_fim"], "%Y-%m-%d"
        ).date()
        if qr["data_fim"] else None
    )

    # Verifica se a campanha está encerrada,
    # ainda não começou ou foi desativada manualmente.
    encerrada = (
        not qr["ativa"]
        or (data_fim is not None and hoje > data_fim)
    )

    ainda_nao_iniciou = (
        data_inicio is not None
        and hoje < data_inicio
    )

    if encerrada or ainda_nao_iniciou:
        return render_template(
            "campanha_inativa.html",
            qr=qr
        )

    # Sorteia um desafio aleatório ou recupera
    # o que já foi sorteado nesta sessão.
    categoria = qr["categoria"] or "frases"
    session_key = f"desafio_sorteado_{codigo}"

    desafio_id = session.get(session_key)
    desafio = None

    if desafio_id:
        desafio = obter_desafio_por_id(
            desafio_id, categoria
        )

    if not desafio:
        desafio = sortear_desafio(categoria)

        if not desafio:
            return render_template(
                "mensagem.html",
                erro="Nenhum desafio disponível."
            ), 404

        session[session_key] = desafio["id"]

    template_name = desafio.get(
        "template",
        "desafio_halloween.html"
    )

    return render_template(
        template_name,
        qr=qr,
        desafio=desafio,
        codigo=codigo
    )


@app.route("/participar/<codigo>", methods=["GET", "POST"])
def participar(codigo):

    if request.method == "POST" and not permitir_requisicao("participacao", 60, 600):
        return make_response(
            "Muitas tentativas de cadastro. Aguarde alguns minutos e tente novamente.", 429
        )

    connection = get_connection()

    qr = connection.execute(
        """
        SELECT
            qr_codes.*,
            campanhas.nome AS campanha_nome,
            campanhas.semana,
            campanhas.frase,
            campanhas.traducao,
            campanhas.ativa,
            locais.nome AS local_nome
        FROM qr_codes
        INNER JOIN campanhas
            ON campanhas.id = qr_codes.campanha_id
        INNER JOIN locais
            ON locais.id = qr_codes.local_id
        WHERE qr_codes.codigo = ?
          AND campanhas.ativa = 1
          AND locais.ativo = 1
        """,
        (codigo,)
    ).fetchone()

    if not qr:
        connection.close()

        return render_template(
            "mensagem.html",
            erro="Mensagem não encontrada."
        ), 404

    if not session.get(f"desafio_acertado_{codigo}"):
        connection.close()
        flash("Acerte o desafio antes de liberar seu cadastro.", "error")
        return redirect(url_for("mensagem", codigo=codigo))

    if request.method == "POST":

        nome = request.form.get("nome", "").strip()
        whatsapp = request.form.get("whatsapp", "").strip()
        email = request.form.get("email", "").strip()
        idade = request.form.get("idade", "").strip()
        participacao_confirmada = request.form.get("participacao_confirmada")

        if (not nome or not whatsapp or not email or not idade
                or not participacao_confirmada):
            connection.close()

            flash(
                "Preencha os campos obrigatórios e confirme sua participação e autorização de contato para continuar.",
                "error"
            )

            return render_template(
                "participar.html",
                qr=qr
            )

        try:
            idade = int(idade)
            if not 3 <= idade <= 120:
                raise ValueError
        except ValueError:
            connection.close()
            flash("Informe uma idade válida.", "error")
            return render_template("participar.html", qr=qr)

        if len(nome) > 120 or len(whatsapp) > 32 or len(email) > 254:
            connection.close()
            flash("Revise os campos: um dos valores excede o limite permitido.", "error")
            return render_template("participar.html", qr=qr)

        digitos_whatsapp = "".join(caractere for caractere in whatsapp if caractere.isdigit())
        if len(digitos_whatsapp) not in (10, 11):
            connection.close()
            flash("Informe um WhatsApp válido com DDD.", "error")
            return render_template("participar.html", qr=qr)

        if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            connection.close()
            flash("Informe um e-mail válido.", "error")
            return render_template("participar.html", qr=qr)

        usuario = connection.execute(
            """
            SELECT *
            FROM usuarios
            WHERE whatsapp = ?
            """,
            (whatsapp,)
        ).fetchone()

        if usuario:
            usuario_id = usuario["id"]

            # Atualiza dados caso tenham mudado
            connection.execute(
                """
                UPDATE usuarios
                SET nome = ?, email = ?, idade = ?
                WHERE id = ?
                """,
                (
                    nome,
                    email,
                    idade,
                    usuario_id
                )
            )

        else:
            cursor = connection.execute(
                """
                INSERT INTO usuarios
                (nome, whatsapp, email, idade)
                VALUES (?, ?, ?, ?)
                RETURNING id
                """,
                (
                    nome,
                    whatsapp,
                    email,
                    idade
                )
            )

            # RETURNING id funciona em SQLite moderno e PostgreSQL; evita depender
            # do cursor.lastrowid, que não é equivalente nos dois drivers.
            usuario_id = cursor.fetchone()["id"]

        # Verifica se já encontrou essa campanha
        ja_encontrou = connection.execute(
            """
            SELECT id
            FROM descobertas
            WHERE usuario_id = ?
            AND campanha_id = ?
            """,
            (
                usuario_id,
                qr["campanha_id"]
            )
        ).fetchone()

        if not ja_encontrou:

            connection.execute(
                """
                INSERT INTO descobertas
                (
                    usuario_id,
                    campanha_id,
                    local_id,
                    qr_code_id
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    usuario_id,
                    qr["campanha_id"],
                    qr["local_id"],
                    qr["id"]
                )
            )

        registrar_consentimento(
            connection, usuario_id, "participacao_e_mensagens", PARTICIPATION_CONSENT_TEXT,
            versao=CONSENT_TEXT_VERSION,
        )
        if idade < 18:
            registrar_consentimento(
                connection, usuario_id, "responsavel_legal", GUARDIAN_CONSENT_TEXT,
                versao=CONSENT_TEXT_VERSION,
            )

        connection.commit()
        connection.close()

        criar_pass_se_necessario(usuario_id)

        total = quantidade_descobertas(usuario_id)

        # Não guardar nome/telefone/e-mail no cookie assinado do navegador.
        session.pop("ultimo_lead_nome", None)
        session["contato_autorizado"] = True

        return redirect(
            url_for("nada")
        )

    connection.close()

    return render_template(
        "participar.html",
        qr=qr
    )


@app.route("/e/<codigo>/responder", methods=["POST"])
def responder_desafio(codigo):
    """Valida o desafio usando o desafio sorteado na sessão."""
    if not permitir_requisicao("desafio", 120, 300):
        response = jsonify({"ok": False, "mensagem": "Muitas tentativas. Aguarde e tente novamente."})
        response.status_code = 429
        response.headers["Retry-After"] = "300"
        return response

    session_key = f"desafio_sorteado_{codigo}"
    desafio_id = session.get(session_key)

    if not desafio_id:
        return jsonify({"ok": False, "mensagem": "Este desafio não está disponível."}), 404

    # Busca a categoria da campanha
    connection = get_connection()
    qr = connection.execute(
        """
        SELECT campanhas.categoria
        FROM qr_codes
        INNER JOIN campanhas ON campanhas.id = qr_codes.campanha_id
        INNER JOIN locais ON locais.id = qr_codes.local_id
        WHERE qr_codes.codigo = ? AND campanhas.ativa = 1 AND locais.ativo = 1
        """,
        (codigo,)
    ).fetchone()
    connection.close()

    if not qr:
        return jsonify({"ok": False, "mensagem": "Este desafio não está disponível."}), 404

    categoria = qr["categoria"] or "frases"
    desafio = obter_desafio_por_id(desafio_id, categoria)

    if not desafio:
        return jsonify({"ok": False, "mensagem": "Desafio não encontrado."}), 404

    letra_informada = request.form.get("resposta", "").strip().upper()
    letra_correta = desafio["resposta_correta"]

    if letra_informada == letra_correta:
        session[f"desafio_acertado_{codigo}"] = True
        return jsonify({"ok": True, "url": url_for("participar", codigo=codigo)})

    return jsonify({
        "ok": False,
        "mensagem": "Não foi dessa vez! Tente outra alternativa. 👻"
    })


@app.route("/nada")
def nada():
    contato_autorizado = bool(session.pop("contato_autorizado", False))
    session.pop("ultimo_lead_nome", None)
    return render_template(
        "nada.html",
        nome="",
        contato_autorizado=contato_autorizado,
        instagram_url="https://www.instagram.com/knnparaisopolis/"
    )


# =========================================================
# ADMIN - LOGIN
# =========================================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST" and not permitir_requisicao("admin_login", 8, 900):
        flash("Muitas tentativas de acesso. Aguarde 15 minutos e tente novamente.", "error")
        return make_response(render_template("admin/login.html"), 429)

    if session.get("admin_logged"):
        return redirect(
            url_for("admin_dashboard")
        )

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        if (
            hmac.compare_digest(username, ADMIN_USERNAME)
            and hmac.compare_digest(password, ADMIN_PASSWORD)
        ):
            # Rotaciona o conteúdo da sessão ao autenticar para reduzir fixation.
            session.clear()
            session.permanent = True
            session["admin_logged"] = True

            return redirect(
                url_for("admin_dashboard")
            )

        flash(
            "Usuário ou senha incorretos.",
            "error"
        )

    return render_template(
        "admin/login.html"
    )


@app.route("/admin/logout", methods=["POST"])
def admin_logout():

    session.clear()

    return redirect(
        url_for("admin_login")
    )


# =========================================================
# ADMIN - DASHBOARD
# =========================================================

@app.route("/admin")
@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():

    connection = get_connection()

    campanhas_ativas = connection.execute(
        """
        SELECT COUNT(*) AS total
        FROM campanhas
        WHERE ativa = 1
        """
    ).fetchone()["total"]

    participantes = connection.execute(
        """
        SELECT COUNT(*) AS total
        FROM usuarios
        """
    ).fetchone()["total"]

    descobertas = connection.execute(
        """
        SELECT COUNT(*) AS total
        FROM descobertas
        """
    ).fetchone()["total"]

    passes = connection.execute(
        """
        SELECT COUNT(*) AS total
        FROM premios
        """
    ).fetchone()["total"]

    locais_ativos = connection.execute(
        "SELECT COUNT(*) AS total FROM locais WHERE ativo = 1"
    ).fetchone()["total"]

    campanha_atual = connection.execute(
        """
        SELECT
            campanhas.*,
            COUNT(DISTINCT descobertas.id) AS total_descobertas,
            COUNT(DISTINCT qr_codes.id) AS total_qrs
        FROM campanhas
        LEFT JOIN descobertas
            ON descobertas.campanha_id = campanhas.id
        LEFT JOIN qr_codes
            ON qr_codes.campanha_id = campanhas.id
        WHERE campanhas.ativa = 1
        GROUP BY campanhas.id
        ORDER BY campanhas.id DESC
        LIMIT 1
        """
    ).fetchone()

    connection.close()

    return render_template(
        "admin/dashboard.html",
        campanhas_ativas=campanhas_ativas,
        participantes=participantes,
        descobertas=descobertas,
        passes=passes,
        locais_ativos=locais_ativos,
        campanha_atual=campanha_atual
    )


# =========================================================
# ADMIN - CAMPANHAS
# =========================================================

@app.route("/admin/campanhas")
@admin_required
def campanhas():

    connection = get_connection()

    lista = connection.execute(
        """
        SELECT
            campanhas.*,
            COUNT(descobertas.id) AS total_descobertas
        FROM campanhas
        LEFT JOIN descobertas
            ON descobertas.campanha_id = campanhas.id
        GROUP BY campanhas.id
        ORDER BY campanhas.semana
        """
    ).fetchall()

    connection.close()

    return render_template(
        "admin/campanhas.html",
        campanhas=lista
    )


@app.route("/admin/campanhas/nova", methods=["GET", "POST"])
@admin_required
def nova_campanha():

    if request.method == "POST":

        nome = request.form.get("nome", "").strip()
        categoria = request.form.get("categoria", "frases").strip()
        data_inicio = request.form.get("data_inicio", "").strip() or None
        data_fim = request.form.get("data_fim", "").strip() or None
        ativa = 1 if request.form.get("ativa") else 0

        if not nome or len(nome) > 150:
            flash("Preencha um nome válido para a campanha.", "error")
            return render_template(
                "admin/campanha_form.html",
                campanha=None,
                categorias=CATEGORIAS,
                desafios_preview=DESAFIOS.get(categoria, DESAFIOS["frases"])
            )

        connection = get_connection()

        max_semana = connection.execute(
            "SELECT COALESCE(MAX(semana), 0) AS max_s FROM campanhas"
        ).fetchone()["max_s"]
        semana = max_semana + 1

        codigo_campanha = gerar_codigo()

        cursor = connection.execute(
            """
            INSERT INTO campanhas
            (codigo, nome, semana, frase, traducao, categoria, data_inicio, data_fim, ativa)
            VALUES (?, ?, ?, '', '', ?, ?, ?, ?)
            RETURNING id
            """,
            (codigo_campanha, nome, semana, categoria, data_inicio, data_fim, ativa)
        )
        campanha_id = cursor.fetchone()["id"]

        # Auto-gerar QR Code para a campanha
        codigo_qr = gerar_codigo()

        # Criar local genérico se não existir
        local_generico = connection.execute(
            "SELECT id FROM locais WHERE nome = 'Geral' LIMIT 1"
        ).fetchone()
        if not local_generico:
            cursor_local = connection.execute(
                "INSERT INTO locais (nome, endereco, parceiro) VALUES ('Geral', '', '') RETURNING id"
            )
            local_id = cursor_local.fetchone()["id"]
        else:
            local_id = local_generico["id"]

        connection.execute(
            "INSERT INTO qr_codes (codigo, campanha_id, local_id) VALUES (?, ?, ?)",
            (codigo_qr, campanha_id, local_id)
        )

        connection.commit()
        connection.close()

        # Gerar arte do QR Code
        campanha_dict = {"semana": semana, "frase": f"CAMPANHA: {nome}", "nome": nome}
        local_dict = {"nome": "QR Code Principal", "parceiro": None}
        gerar_arte_qrcode(codigo_qr, campanha_dict, local_dict)

        flash("Campanha criada com sucesso! QR Code gerado automaticamente.", "success")
        return redirect(url_for("campanhas"))

    categoria_default = "frases"
    return render_template(
        "admin/campanha_form.html",
        campanha=None,
        categorias=CATEGORIAS,
        desafios_preview=DESAFIOS.get(categoria_default, []),
        todos_desafios=DESAFIOS
    )


@app.route("/admin/campanhas/<int:campanha_id>/editar", methods=["GET", "POST"])
@admin_required
def editar_campanha(campanha_id):

    connection = get_connection()

    campanha = connection.execute(
        """
        SELECT *
        FROM campanhas
        WHERE id = ?
        """,
        (campanha_id,)
    ).fetchone()

    if not campanha:
        connection.close()

        flash(
            "Campanha não encontrada.",
            "error"
        )

        return redirect(
            url_for("campanhas")
        )

    if request.method == "POST":

        nome = request.form.get("nome", "").strip()
        categoria = request.form.get("categoria", "frases").strip()
        data_inicio = request.form.get("data_inicio", "").strip() or None
        data_fim = request.form.get("data_fim", "").strip() or None
        ativa = 1 if request.form.get("ativa") else 0

        if not nome or len(nome) > 150:
            connection.close()
            flash("Preencha um nome válido para a campanha.", "error")
            return render_template(
                "admin/campanha_form.html",
                campanha=campanha,
                categorias=CATEGORIAS,
                desafios_preview=DESAFIOS.get(categoria, DESAFIOS["frases"])
            )

        connection.execute(
            """
            UPDATE campanhas
            SET
                nome = ?,
                categoria = ?,
                data_inicio = ?,
                data_fim = ?,
                ativa = ?
            WHERE id = ?
            """,
            (
                nome,
                categoria,
                data_inicio,
                data_fim,
                ativa,
                campanha_id
            )
        )

        connection.commit()
        connection.close()

        flash(
            "Campanha atualizada com sucesso.",
            "success"
        )

        return redirect(
            url_for("campanhas")
        )

    categoria_atual = campanha["categoria"] if "categoria" in campanha.keys() and campanha["categoria"] else "frases"
    connection.close()

    return render_template(
        "admin/campanha_form.html",
        campanha=campanha,
        categorias=CATEGORIAS,
        desafios_preview=DESAFIOS.get(categoria_atual, DESAFIOS["frases"]),
        todos_desafios=DESAFIOS
    )


@app.route("/admin/campanhas/<int:campanha_id>/excluir", methods=["POST"])
@admin_required
def excluir_campanha(campanha_id):
    connection = get_connection()
    qrs = connection.execute(
        "SELECT codigo FROM qr_codes WHERE campanha_id = ?",
        (campanha_id,)
    ).fetchall()
    campanha = connection.execute(
        "SELECT id FROM campanhas WHERE id = ?",
        (campanha_id,)
    ).fetchone()

    if not campanha:
        connection.close()
        flash("Campanha não encontrada.", "error")
        return redirect(url_for("campanhas"))

    connection.execute("DELETE FROM campanhas WHERE id = ?", (campanha_id,))
    connection.commit()
    connection.close()

    for qr in qrs:
        caminho = os.path.join("instance", "qrcodes", f"{qr['codigo']}.png")
        if os.path.exists(caminho):
            os.remove(caminho)

    flash("Campanha e seus QR Codes foram excluídos.", "success")
    return redirect(url_for("campanhas"))


# =========================================================
# ADMIN - LOCAIS
# =========================================================

@app.route("/admin/locais")
@admin_required
def locais():

    connection = get_connection()

    lista = connection.execute(
        """
        SELECT
            locais.*,
            COUNT(qr_codes.id) AS total_qr
        FROM locais
        LEFT JOIN qr_codes
            ON qr_codes.local_id = locais.id
        GROUP BY locais.id
        ORDER BY locais.nome
        """
    ).fetchall()

    connection.close()

    return render_template(
        "admin/locais.html",
        locais=lista
    )


@app.route("/admin/locais/novo", methods=["GET", "POST"])
@admin_required
def novo_local():

    if request.method == "POST":

        nome = request.form.get(
            "nome",
            ""
        ).strip()

        endereco = request.form.get(
            "endereco",
            ""
        ).strip()

        parceiro = request.form.get(
            "parceiro",
            ""
        ).strip()

        if not nome or len(nome) > 120 or len(endereco) > 250 or len(parceiro) > 150:
            flash(
                "Informe o nome do local e respeite os limites dos campos.",
                "error"
            )

            return render_template(
                "admin/local_form.html",
                local=None
            )

        connection = get_connection()

        connection.execute(
            """
            INSERT INTO locais
            (nome, endereco, parceiro)
            VALUES (?, ?, ?)
            """,
            (
                nome,
                endereco,
                parceiro
            )
        )

        connection.commit()
        connection.close()

        flash(
            "Local cadastrado!",
            "success"
        )

        return redirect(
            url_for("locais")
        )

    return render_template(
        "admin/local_form.html",
        local=None
    )


@app.route("/admin/locais/<int:local_id>/excluir", methods=["POST"])
@admin_required
def excluir_local(local_id):
    connection = get_connection()
    qrs = connection.execute(
        "SELECT codigo FROM qr_codes WHERE local_id = ?",
        (local_id,)
    ).fetchall()
    local = connection.execute(
        "SELECT id FROM locais WHERE id = ?",
        (local_id,)
    ).fetchone()

    if not local:
        connection.close()
        flash("Local não encontrado.", "error")
        return redirect(url_for("locais"))

    connection.execute("DELETE FROM locais WHERE id = ?", (local_id,))
    connection.commit()
    connection.close()

    for qr in qrs:
        caminho = os.path.join("instance", "qrcodes", f"{qr['codigo']}.png")
        if os.path.exists(caminho):
            os.remove(caminho)

    flash("Local e seus QR Codes foram excluídos.", "success")
    return redirect(url_for("locais"))


# =========================================================
# ADMIN - QR CODES
# =========================================================

def carregar_fonte(nomes, tamanho):
    """Carrega fontes legíveis no Windows local e no Linux do Render.

    O código antigo procurava fontes apenas no diretório do Windows. No Render,
    isso falhava e o fallback do Pillow tinha tamanho padrão muito pequeno,
    ignorando o tamanho solicitado para a arte do QR Code.
    """
    fontes = []

    # Caminho de fontes do Windows (ambiente local de desenvolvimento).
    windir = os.environ.get("WINDIR")
    if windir:
        fontes.append(os.path.join(windir, "Fonts"))
    elif os.name == "nt":
        fontes.append(os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Fonts"))

    # Caminhos mais comuns em imagens Linux/Debian, como as usadas na hospedagem.
    fontes.extend([
        "/usr/share/fonts/truetype/dejavu",
        "/usr/share/fonts/truetype/liberation2",
        "/usr/share/fonts/truetype/liberation",
        "/usr/share/fonts/truetype/msttcorefonts",
        "/usr/local/share/fonts",
    ])

    # Primeiro tenta exatamente os nomes originalmente solicitados.
    for pasta in fontes:
        for nome in nomes:
            caminho = os.path.join(pasta, nome)
            if os.path.isfile(caminho):
                try:
                    return ImageFont.truetype(caminho, tamanho)
                except (OSError, ValueError):
                    continue

    # Se o servidor Linux não tiver Arial/Segoe UI, usa fontes equivalentes.
    nomes_lower = " ".join(nomes).lower()
    negrito = any(marca in nomes_lower for marca in ("bd", "bold", "segoeuib"))
    alternativas = (
        [
            "DejaVuSans-Bold.ttf",
            "LiberationSans-Bold.ttf",
            "Lato-Bold.ttf",
        ] if negrito else [
            "DejaVuSans.ttf",
            "LiberationSans-Regular.ttf",
            "Lato-Regular.ttf",
        ]
    )
    for pasta in fontes:
        for nome in alternativas:
            caminho = os.path.join(pasta, nome)
            if os.path.isfile(caminho):
                try:
                    return ImageFont.truetype(caminho, tamanho)
                except (OSError, ValueError):
                    continue

    # Pillow >= 10.1 aceita tamanho no fallback interno. Isso evita que o
    # texto caia para a fonte bitmap minúscula padrão de aproximadamente 10 px.
    try:
        return ImageFont.load_default(size=tamanho)
    except TypeError:
        # Compatibilidade com ambientes locais antigos; o requirements.txt
        # da aplicação instala uma versão recente do Pillow no deploy.
        return ImageFont.load_default()


def quebrar_texto(texto, fonte, max_largura, draw):
    palavras = (texto or "").split()
    linhas = []
    linha_atual = []
    for palavra in palavras:
        teste = " ".join(linha_atual + [palavra])
        try:
            bbox = draw.textbbox((0, 0), teste, font=fonte)
            largura = bbox[2] - bbox[0]
        except Exception:
            largura = len(teste) * 12
        if largura <= max_largura:
            linha_atual.append(palavra)
        else:
            if linha_atual:
                linhas.append(" ".join(linha_atual))
                linha_atual = [palavra]
            else:
                linhas.append(palavra)
                linha_atual = []
    if linha_atual:
        linhas.append(" ".join(linha_atual))
    return linhas or [texto or ""]


def gerar_arte_qrcode(codigo, campanha, local):
    """
    Gera arte pronta para impressão com o QR Code e a frase da semana em destaque.
    """
    largura_canvas, altura_canvas = 1080, 1560
    img = Image.new("RGB", (largura_canvas, altura_canvas), color="#FBFBFB")
    draw = ImageDraw.Draw(img)

    COR_VERMELHO = "#ED1B2F"
    COR_PRETO = "#111827"
    COR_CINZA = "#4B5563"
    COR_CINZA_CLARO = "#E5E7EB"
    COR_BRANCO = "#FFFFFF"

    # 1. Header KNN
    draw.rectangle([(0, 0), (largura_canvas, 140)], fill=COR_VERMELHO)
    fonte_knn = carregar_fonte(["arialbd.ttf", "segoeuib.ttf"], 46)
    fonte_sub = carregar_fonte(["arial.ttf", "segoeui.ttf"], 22)
    draw.text((largura_canvas / 2, 50), "KNN IDIOMAS", fill=COR_BRANCO, font=fonte_knn, anchor="mm")

    semana_num = campanha["semana"] if isinstance(campanha, dict) or hasattr(campanha, "__getitem__") else 1
    draw.text(
        (largura_canvas / 2, 100),
        f"INGLÊS SECRETO · SEMANA {semana_num}",
        fill="#FFE4E6",
        font=fonte_sub,
        anchor="mm"
    )

    # 2. Box Frase da Semana
    frase_raw = ""
    if isinstance(campanha, dict) or hasattr(campanha, "__getitem__"):
        try:
            frase_raw = campanha["frase"] or campanha["nome"]
        except Exception:
            frase_raw = "DESCUBRA SEU ENIGMA"
    if not frase_raw:
        frase_raw = "DESCUBRA SEU ENIGMA"

    frase = frase_raw.strip().upper()

    if len(frase) > 35:
        tam_frase = 46
    elif len(frase) > 20:
        tam_frase = 54
    else:
        tam_frase = 64

    fonte_frase = carregar_fonte(["arialbd.ttf", "segoeuib.ttf"], tam_frase)
    linhas_frase = quebrar_texto(frase, fonte_frase, largura_canvas - 180, draw)

    box_y1 = 170
    altura_texto = len(linhas_frase) * (tam_frase + 16)
    box_altura = max(220, altura_texto + 100)
    box_y2 = box_y1 + box_altura

    draw.rounded_rectangle(
        [(60, box_y1), (largura_canvas - 60, box_y2)],
        radius=20,
        fill=COR_BRANCO,
        outline="#FCA5A5",
        width=3
    )

    fonte_tag = carregar_fonte(["arialbd.ttf", "segoeuib.ttf"], 22)
    draw.text(
        (largura_canvas / 2, box_y1 + 40),
        f"MISSÃO DA SEMANA {semana_num} · HALLOWEEN SECRETO",
        fill=COR_VERMELHO,
        font=fonte_tag,
        anchor="mm"
    )

    y_inicio_frase = box_y1 + 80 + int((box_altura - 80 - altura_texto) / 2) + int(tam_frase / 2)
    for i, linha in enumerate(linhas_frase):
        y_linha = y_inicio_frase + i * (tam_frase + 16)
        draw.text((largura_canvas / 2, y_linha), linha, fill=COR_PRETO, font=fonte_frase, anchor="mm")

    # 3. QR Code
    url = f"{BASE_URL}/e/{codigo}"
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=16,
        border=2
    )
    qr.add_data(url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#111827", back_color="white").convert("RGB")

    qr_tamanho = 600
    qr_img = qr_img.resize((qr_tamanho, qr_tamanho))

    qr_x = int((largura_canvas - qr_tamanho) / 2)
    qr_y = box_y2 + 40

    draw.rounded_rectangle(
        [(qr_x - 18, qr_y - 18), (qr_x + qr_tamanho + 18, qr_y + qr_tamanho + 18)],
        radius=22,
        fill=COR_BRANCO,
        outline=COR_CINZA_CLARO,
        width=2
    )
    img.paste(qr_img, (qr_x, qr_y))

    # 4. Instruções de Participação
    fonte_inst_tit = carregar_fonte(["arialbd.ttf", "segoeuib.ttf"], 32)
    fonte_inst_desc = carregar_fonte(["arial.ttf", "segoeui.ttf"], 24)

    y_inst = qr_y + qr_tamanho + 55
    draw.text(
        (largura_canvas / 2, y_inst),
        "Aponte a câmera do celular para o QR Code",
        fill=COR_PRETO,
        font=fonte_inst_tit,
        anchor="mm"
    )
    draw.text(
        (largura_canvas / 2, y_inst + 45),
        "Descubra o significado da frase e concorra a prêmios na KNN!",
        fill=COR_CINZA,
        font=fonte_inst_desc,
        anchor="mm"
    )

    # 5. Rodapé
    draw.rectangle([(0, altura_canvas - 110), (largura_canvas, altura_canvas)], fill="#F3F4F6")
    draw.line([(0, altura_canvas - 110), (largura_canvas, altura_canvas - 110)], fill=COR_CINZA_CLARO, width=2)

    local_nome = local["nome"] if local and (isinstance(local, dict) or hasattr(local, "__getitem__")) else "Ponto da Missão"
    parceiro = local["parceiro"] if local and (isinstance(local, dict) or hasattr(local, "__getitem__")) else None
    local_texto = f"Ponto: {local_nome}" + (f" · {parceiro}" if parceiro else "")
    if len(local_texto) > 45:
        local_texto = local_texto[:42] + "..."

    fonte_rodape = carregar_fonte(["arial.ttf", "segoeui.ttf"], 20)
    fonte_rodape_bold = carregar_fonte(["arialbd.ttf", "segoeuib.ttf"], 20)

    draw.text((60, altura_canvas - 55), local_texto, fill=COR_PRETO, font=fonte_rodape_bold, anchor="lm")
    draw.text((largura_canvas - 60, altura_canvas - 55), f"Código: {codigo}", fill=COR_CINZA, font=fonte_rodape, anchor="rm")

    pasta = os.path.join("instance", "qrcodes")
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, f"{codigo}.png")
    img.save(caminho, quality=95)
    return caminho


@app.route("/admin/qr/<int:campanha_id>/<int:local_id>/gerar", methods=["POST"])
@admin_required
def gerar_qr(campanha_id, local_id):

    if not permitir_requisicao("gerar_qr", 30, 600):
        return make_response("Muitas solicitações. Aguarde e tente novamente.", 429)

    connection = get_connection()

    campanha = connection.execute(
        """
        SELECT *
        FROM campanhas
        WHERE id = ?
        """,
        (campanha_id,)
    ).fetchone()

    local = connection.execute(
        """
        SELECT *
        FROM locais
        WHERE id = ?
        """,
        (local_id,)
    ).fetchone()

    if not campanha or not local:
        connection.close()

        flash(
            "Campanha ou local não encontrado.",
            "error"
        )

        return redirect(
            url_for("campanhas")
        )

    qr_existente = connection.execute(
        "SELECT codigo FROM qr_codes WHERE campanha_id = ? AND local_id = ?",
        (campanha_id, local_id)
    ).fetchone()

    if qr_existente:
        connection.close()
        flash("Este local já possui um QR Code para esta campanha.", "error")
        return redirect(url_for("gerenciar_qr", campanha_id=campanha_id))

    codigo = gerar_codigo()

    connection.execute(
        """
        INSERT INTO qr_codes
        (
            codigo,
            campanha_id,
            local_id
        )
        VALUES (?, ?, ?)
        """,
        (
            codigo,
            campanha_id,
            local_id
        )
    )

    connection.commit()
    connection.close()

    caminho = gerar_arte_qrcode(codigo, campanha, local)

    return send_file(
        caminho,
        mimetype="image/png",
        as_attachment=True,
        download_name=f"qr-ingles-secreto-semana{campanha['semana']}-{codigo}.png"
    )


@app.route("/admin/qr/<codigo>/download")
@admin_required
def download_qr(codigo):
    connection = get_connection()
    qr = connection.execute(
        """
        SELECT
            qr_codes.*,
            campanhas.semana,
            campanhas.frase,
            campanhas.nome AS campanha_nome,
            locais.nome AS local_nome,
            locais.parceiro
        FROM qr_codes
        INNER JOIN campanhas ON campanhas.id = qr_codes.campanha_id
        INNER JOIN locais ON locais.id = qr_codes.local_id
        WHERE qr_codes.codigo = ?
        """,
        (codigo,)
    ).fetchone()
    connection.close()

    if not qr:
        flash("QR Code não encontrado.", "error")
        return redirect(url_for("campanhas"))

    campanha = {"semana": qr["semana"], "frase": qr["frase"], "nome": qr["campanha_nome"]}
    local = {"nome": qr["local_nome"], "parceiro": qr["parceiro"]}
    caminho = gerar_arte_qrcode(codigo, campanha, local)

    return send_file(
        caminho,
        mimetype="image/png",
        as_attachment=True,
        download_name=f"qr-ingles-secreto-semana{qr['semana']}-{codigo}.png"
    )


@app.route("/admin/qr/<codigo>/imagem")
@admin_required
def imagem_qr(codigo):
    connection = get_connection()
    qr = connection.execute(
        """
        SELECT
            qr_codes.*,
            campanhas.semana,
            campanhas.frase,
            campanhas.nome AS campanha_nome,
            locais.nome AS local_nome,
            locais.parceiro
        FROM qr_codes
        INNER JOIN campanhas ON campanhas.id = qr_codes.campanha_id
        INNER JOIN locais ON locais.id = qr_codes.local_id
        WHERE qr_codes.codigo = ?
        """,
        (codigo,)
    ).fetchone()
    connection.close()

    if not qr:
        return "Não encontrado", 404

    caminho = os.path.join("instance", "qrcodes", f"{codigo}.png")
    if not os.path.exists(caminho):
        campanha = {"semana": qr["semana"], "frase": qr["frase"], "nome": qr["campanha_nome"]}
        local = {"nome": qr["local_nome"], "parceiro": qr["parceiro"]}
        caminho = gerar_arte_qrcode(codigo, campanha, local)

    return send_file(caminho, mimetype="image/png")


@app.route("/admin/qr/<codigo>/imprimir")
@admin_required
def imprimir_qr(codigo):
    connection = get_connection()
    qr = connection.execute(
        """
        SELECT
            qr_codes.*,
            campanhas.id AS campanha_id,
            campanhas.semana,
            campanhas.frase,
            campanhas.traducao,
            campanhas.nome AS campanha_nome,
            locais.nome AS local_nome,
            locais.parceiro,
            locais.endereco
        FROM qr_codes
        INNER JOIN campanhas ON campanhas.id = qr_codes.campanha_id
        INNER JOIN locais ON locais.id = qr_codes.local_id
        WHERE qr_codes.codigo = ?
        """,
        (codigo,)
    ).fetchone()
    connection.close()

    if not qr:
        flash("QR Code não encontrado.", "error")
        return redirect(url_for("campanhas"))

    campanha = {"semana": qr["semana"], "frase": qr["frase"], "nome": qr["campanha_nome"]}
    local = {"nome": qr["local_nome"], "parceiro": qr["parceiro"]}
    gerar_arte_qrcode(codigo, campanha, local)

    return render_template("admin/imprimir_qr.html", qr=qr)


@app.route("/admin/qr/<int:qr_id>/excluir", methods=["POST"])
@admin_required
def excluir_qr(qr_id):
    connection = get_connection()
    qr = connection.execute(
        "SELECT codigo, campanha_id FROM qr_codes WHERE id = ?",
        (qr_id,)
    ).fetchone()

    if not qr:
        connection.close()
        flash("QR Code não encontrado.", "error")
        return redirect(url_for("campanhas"))

    connection.execute("DELETE FROM qr_codes WHERE id = ?", (qr_id,))
    connection.commit()
    connection.close()

    caminho = os.path.join("instance", "qrcodes", f"{qr['codigo']}.png")
    if os.path.exists(caminho):
        os.remove(caminho)

    flash("QR Code excluído. Você pode gerar outro para este local.", "success")
    return redirect(url_for("gerenciar_qr", campanha_id=qr["campanha_id"]))


@app.route("/admin/qr/<int:campanha_id>")
@admin_required
def gerenciar_qr(campanha_id):

    connection = get_connection()

    campanha = connection.execute(
        """
        SELECT *
        FROM campanhas
        WHERE id = ?
        """,
        (campanha_id,)
    ).fetchone()

    locais = connection.execute(
        """
        SELECT *
        FROM locais
        WHERE ativo = 1
        ORDER BY nome
        """
    ).fetchall()

    qrs = connection.execute(
        """
        SELECT
            qr_codes.*,
            locais.nome AS local_nome,
            locais.parceiro
        FROM qr_codes
        INNER JOIN locais
            ON locais.id = qr_codes.local_id
        WHERE qr_codes.campanha_id = ?
        ORDER BY qr_codes.id DESC
        """,
        (campanha_id,)
    ).fetchall()

    connection.close()

    return render_template(
        "admin/locais.html",
        locais=locais,
        campanha_qr=campanha,
        qrs=qrs
    )


# =========================================================
# ADMIN - PARTICIPANTES
# =========================================================

@app.route("/admin/participantes")
@admin_required
def participantes():

    connection = get_connection()

    lista = connection.execute(
        """
        SELECT
            usuarios.*,
            COUNT(descobertas.id) AS total_descobertas
        FROM usuarios
        LEFT JOIN descobertas
            ON descobertas.usuario_id = usuarios.id
        GROUP BY usuarios.id
        ORDER BY total_descobertas DESC
        """
    ).fetchall()

    connection.close()

    return render_template(
        "admin/participantes.html",
        participantes=lista,
        pass_required=ENGLISH_PASS_REQUIRED
    )


# =========================================================
# ADMIN - DESCOBERTAS
# =========================================================

@app.route("/admin/descobertas")
@admin_required
def descobertas():

    connection = get_connection()

    lista = connection.execute(
        """
        SELECT
            descobertas.*,
            usuarios.nome AS usuario_nome,
            usuarios.whatsapp,
            campanhas.frase,
            campanhas.semana,
            locais.nome AS local_nome,
            locais.parceiro,
            qr_codes.codigo AS qr_codigo
        FROM descobertas
        INNER JOIN usuarios
            ON usuarios.id = descobertas.usuario_id
        INNER JOIN campanhas
            ON campanhas.id = descobertas.campanha_id
        INNER JOIN locais
            ON locais.id = descobertas.local_id
        INNER JOIN qr_codes
            ON qr_codes.id = descobertas.qr_code_id
        ORDER BY descobertas.data_hora DESC
        """
    ).fetchall()

    connection.close()

    return render_template(
        "admin/descobertas.html",
        descobertas=lista
    )


# =========================================================
# ADMIN - ENGLISH PASS
# =========================================================

@app.route("/admin/pass")
@admin_required
def admin_pass():

    connection = get_connection()

    premios = connection.execute(
        """
        SELECT
            premios.*,
            usuarios.nome AS usuario_nome,
            usuarios.whatsapp,
            recompensas.nome AS recompensa_nome
        FROM premios
        INNER JOIN usuarios
            ON usuarios.id = premios.usuario_id
        INNER JOIN recompensas
            ON recompensas.id = premios.recompensa_id
        ORDER BY premios.data_desbloqueio DESC
        """
    ).fetchall()

    recompensas = connection.execute(
        """
        SELECT *
        FROM recompensas
        ORDER BY id
        """
    ).fetchall()

    connection.close()

    return render_template(
        "admin/pass.html",
        premios=premios,
        recompensas=recompensas
    )


@app.route("/admin/pass/<int:premio_id>/utilizar", methods=["POST"])
@admin_required
def utilizar_premio(premio_id):

    connection = get_connection()

    connection.execute(
        """
        UPDATE premios
        SET
            status = 'utilizado',
            data_utilizacao = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (premio_id,)
    )

    connection.commit()
    connection.close()

    flash(
        "Recompensa marcada como utilizada.",
        "success"
    )

    return redirect(
        url_for("admin_pass")
    )


# =========================================================
# EXECUÇÃO
# =========================================================

if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=os.getenv("FLASK_DEBUG", "").lower() == "true" and not IS_PRODUCTION,
    )
