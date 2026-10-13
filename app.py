from functools import wraps
from datetime import datetime
import os
import random
import string

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
    jsonify
)

from config import (
    SECRET_KEY,
    ADMIN_USERNAME,
    ADMIN_PASSWORD,
    BASE_URL,
    ENGLISH_PASS_REQUIRED
)

from database import get_connection, init_db


app = Flask(__name__)
app.secret_key = SECRET_KEY

init_db()


# =========================================================
# UTILITÁRIOS
# =========================================================

def gerar_codigo(tamanho=4):
    caracteres = string.ascii_uppercase + string.digits

    while True:
        codigo = "".join(
            random.choice(caracteres)
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


@app.route("/e/<codigo>", methods=["GET", "POST"])
def mensagem(codigo):

    connection = get_connection()

    qr = connection.execute(
        """
        SELECT
            qr_codes.*,
            campanhas.nome AS campanha_nome,
            campanhas.semana,
            campanhas.frase,
            campanhas.traducao,
            campanhas.opcao_a,
            campanhas.opcao_b,
            campanhas.opcao_c,
            campanhas.resposta_correta,
            campanhas.ativa,
            locais.nome AS local_nome,
            locais.parceiro
        FROM qr_codes
        INNER JOIN campanhas
            ON campanhas.id = qr_codes.campanha_id
        INNER JOIN locais
            ON locais.id = qr_codes.local_id
        WHERE qr_codes.codigo = ?
        """,
        (codigo,)
    ).fetchone()

    connection.close()

    if not qr:
        return render_template(
            "mensagem.html",
            erro="Mensagem não encontrada."
        ), 404

    # Garante opções válidas com fallback inteligente
    opcao_a = qr["opcao_a"] or (qr["traducao"].split("|")[0].strip() if qr["traducao"] else "Vejo você lá")
    opcao_b = qr["opcao_b"] or "Onde você está?"
    opcao_c = qr["opcao_c"] or "Bom te ver ontem"
    resposta_correta = (qr["resposta_correta"] or "A").strip().upper()

    opcoes = [
        {"letra": "A", "texto": opcao_a},
        {"letra": "B", "texto": opcao_b},
        {"letra": "C", "texto": opcao_c}
    ]

    return render_template(
        "mensagem.html",
        qr=qr,
        opcoes=opcoes,
        resposta_correta=resposta_correta
    )


@app.route("/participar/<codigo>", methods=["GET", "POST"])
def participar(codigo):

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
        consentimento = request.form.get("consentimento")

        if not nome or not whatsapp or not email or not idade or not consentimento:
            connection.close()

            flash(
                "Preencha todos os campos e autorize o contato para continuar.",
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

        connection.commit()
        connection.close()

        criar_pass_se_necessario(usuario_id)

        total = quantidade_descobertas(usuario_id)

        session["ultimo_lead_nome"] = nome

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
    """Valida o desafio no servidor com suporte a múltipla escolha (A, B, C)."""
    connection = get_connection()
    qr = connection.execute(
        """
        SELECT
            campanhas.traducao,
            campanhas.opcao_a,
            campanhas.opcao_b,
            campanhas.opcao_c,
            campanhas.resposta_correta
        FROM qr_codes
        INNER JOIN campanhas ON campanhas.id = qr_codes.campanha_id
        WHERE qr_codes.codigo = ? AND campanhas.ativa = 1
        """,
        (codigo,)
    ).fetchone()
    connection.close()

    if not qr:
        return jsonify({"ok": False, "mensagem": "Este desafio não está disponível."}), 404

    resposta_bruta = request.form.get("resposta", "").strip()
    resposta_norm = normalizar_resposta(resposta_bruta)
    letra_informada = resposta_bruta.upper()
    letra_correta = (qr["resposta_correta"] or "A").strip().upper()

    acertou = False
    # Verificação direta por letra A, B ou C
    if letra_informada in ["A", "B", "C"] and letra_informada == letra_correta:
        acertou = True
    else:
        # Verificação pelo texto da opção correta
        texto_correto = ""
        if letra_correta == "A":
            texto_correto = qr["opcao_a"] or qr["traducao"]
        elif letra_correta == "B":
            texto_correto = qr["opcao_b"]
        elif letra_correta == "C":
            texto_correto = qr["opcao_c"]

        respostas_validas = []
        if texto_correto:
            respostas_validas.append(normalizar_resposta(texto_correto))
        if qr["traducao"]:
            respostas_validas.extend([normalizar_resposta(item) for item in qr["traducao"].split("|")])

        if resposta_norm and resposta_norm in respostas_validas:
            acertou = True

    if acertou:
        session[f"desafio_acertado_{codigo}"] = True
        return jsonify({"ok": True, "url": url_for("participar", codigo=codigo)})

    return jsonify({
        "ok": False,
        "mensagem": "Não foi dessa vez! Tente outra alternativa."
    })


@app.route("/nada")
def nada():
    nome = session.get("ultimo_lead_nome", "")
    return render_template(
        "nada.html",
        nome=nome,
        instagram_url="https://www.instagram.com/knnparaisopolis/"
    )


@app.route("/admin/capturar-lead", methods=["POST"])
def capturar_lead_login():
    nome = request.form.get("lead_nome", "").strip()
    whatsapp = request.form.get("lead_whatsapp", "").strip()
    email = request.form.get("lead_email", "").strip()

    if not nome or not whatsapp:
        flash("Informe seu nome e WhatsApp para receber as novidades.", "error")
        return redirect(url_for("admin_login"))

    digitos_whatsapp = "".join(caractere for caractere in whatsapp if caractere.isdigit())
    if len(digitos_whatsapp) not in (10, 11):
        flash("Informe um WhatsApp válido com DDD.", "error")
        return redirect(url_for("admin_login"))

    connection = get_connection()
    usuario = connection.execute(
        "SELECT id FROM usuarios WHERE whatsapp = ?",
        (whatsapp,)
    ).fetchone()

    if not usuario:
        connection.execute(
            """
            INSERT INTO usuarios (nome, whatsapp, email, idade)
            VALUES (?, ?, ?, NULL)
            """,
            (nome, whatsapp, email)
        )
        connection.commit()
    connection.close()

    session["ultimo_lead_nome"] = nome
    flash("Contato recebido! A equipe da KNN Paraisópolis vai falar com você no WhatsApp.", "success")
    return redirect(url_for("nada"))


# =========================================================
# ADMIN - LOGIN
# =========================================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

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
            username == ADMIN_USERNAME
            and password == ADMIN_PASSWORD
        ):
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


@app.route("/admin/logout")
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

        nome = request.form.get(
            "nome",
            ""
        ).strip()

        frase = request.form.get(
            "frase",
            ""
        ).strip()

        traducao = request.form.get(
            "traducao",
            ""
        ).strip()

        opcao_a = request.form.get("opcao_a", "").strip()
        opcao_b = request.form.get("opcao_b", "").strip()
        opcao_c = request.form.get("opcao_c", "").strip()
        resposta_correta = request.form.get("resposta_correta", "A").strip().upper()

        if not traducao and opcao_a:
            traducao = opcao_a

        data_inicio = request.form.get(
            "data_inicio",
            ""
        )

        data_fim = request.form.get(
            "data_fim",
            ""
        )

        ativa = 1 if request.form.get(
            "ativa"
        ) else 0

        if not nome or not frase:
            flash(
                "Preencha os campos obrigatórios.",
                "error"
            )

            return render_template(
                "admin/campanha_form.html",
                campanha=None
            )

        connection = get_connection()

        semana_form = request.form.get("semana")
        if semana_form and semana_form.strip().isdigit():
            semana = int(semana_form.strip())
            semana_ja_cadastrada = connection.execute(
                "SELECT id FROM campanhas WHERE semana = ?",
                (semana,)
            ).fetchone()
            if semana_ja_cadastrada:
                connection.close()
                flash("Já existe uma campanha cadastrada para esta semana.", "error")
                return render_template("admin/campanha_form.html", campanha=None)
        else:
            max_semana = connection.execute(
                "SELECT COALESCE(MAX(semana), 0) AS max_s FROM campanhas"
            ).fetchone()["max_s"]
            semana = max_semana + 1

        codigo = gerar_codigo()

        connection = get_connection()

        connection.execute(
            """
            INSERT INTO campanhas
            (
                codigo,
                nome,
                semana,
                frase,
                traducao,
                opcao_a,
                opcao_b,
                opcao_c,
                resposta_correta,
                data_inicio,
                data_fim,
                ativa
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                codigo,
                nome,
                int(semana),
                frase,
                traducao,
                opcao_a,
                opcao_b,
                opcao_c,
                resposta_correta,
                data_inicio,
                data_fim,
                ativa
            )
        )

        connection.commit()
        connection.close()

        flash(
            "Campanha criada com sucesso!",
            "success"
        )

        return redirect(
            url_for("campanhas")
        )

    return render_template(
        "admin/campanha_form.html",
        campanha=None
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

        nome = request.form.get(
            "nome",
            ""
        ).strip()

        semana_form = request.form.get("semana")
        if semana_form and semana_form.strip().isdigit():
            semana = int(semana_form.strip())
        else:
            semana = campanha["semana"]

        frase = request.form.get(
            "frase",
            ""
        ).strip()

        traducao = request.form.get(
            "traducao",
            ""
        ).strip()

        opcao_a = request.form.get("opcao_a", "").strip()
        opcao_b = request.form.get("opcao_b", "").strip()
        opcao_c = request.form.get("opcao_c", "").strip()
        resposta_correta = request.form.get("resposta_correta", "A").strip().upper()

        if not traducao and opcao_a:
            traducao = opcao_a

        data_inicio = request.form.get(
            "data_inicio",
            ""
        )

        data_fim = request.form.get(
            "data_fim",
            ""
        )

        ativa = 1 if request.form.get(
            "ativa"
        ) else 0

        semana_ja_cadastrada = connection.execute(
            "SELECT id FROM campanhas WHERE semana = ? AND id != ?",
            (int(semana), campanha_id)
        ).fetchone()

        if semana_ja_cadastrada:
            connection.close()
            flash("Já existe uma campanha cadastrada para esta semana.", "error")
            return render_template("admin/campanha_form.html", campanha=campanha)

        connection.execute(
            """
            UPDATE campanhas
            SET
                nome = ?,
                semana = ?,
                frase = ?,
                traducao = ?,
                opcao_a = ?,
                opcao_b = ?,
                opcao_c = ?,
                resposta_correta = ?,
                data_inicio = ?,
                data_fim = ?,
                ativa = ?
            WHERE id = ?
            """,
            (
                nome,
                int(semana),
                frase,
                traducao,
                opcao_a,
                opcao_b,
                opcao_c,
                resposta_correta,
                data_inicio,
                data_fim,
                ativa,
                campanha_id
            )
        )

        connection.commit()
        connection.close()

        flash(
            "Campanha atualizada.",
            "success"
        )

        return redirect(
            url_for("campanhas")
        )

    connection.close()

    return render_template(
        "admin/campanha_form.html",
        campanha=campanha
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

        if not nome:
            flash(
                "Informe o nome do local.",
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
    windir = os.environ.get("WINDIR", "C:\\Windows")
    fonts_dir = os.path.join(windir, "Fonts")
    for nome in nomes:
        caminho = os.path.join(fonts_dir, nome)
        if os.path.exists(caminho):
            try:
                return ImageFont.truetype(caminho, tamanho)
            except Exception:
                pass
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
    frase_raw = campanha["frase"] if isinstance(campanha, dict) or hasattr(campanha, "__getitem__") else ""
    frase = (frase_raw or "").strip().upper()

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
        f"MISSÃO DA SEMANA {semana_num} · FRASE SECRETA",
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


@app.route("/admin/qr/<int:campanha_id>/<int:local_id>/gerar")
@admin_required
def gerar_qr(campanha_id, local_id):

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
        host="0.0.0.0",
        port=5000,
        debug=True
    )
