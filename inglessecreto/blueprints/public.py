import re
import unicodedata

from flask import (Blueprint, flash, jsonify, make_response, redirect,
                   render_template, request, session, url_for)

from database import get_connection
from desafios import obter_desafio_por_id

from config import BASE_URL, ENGLISH_PASS_REQUIRED, UNIDADE
from ..security import permitir_requisicao
from ..services.challenges import guardar_historico, sortear_para_navegador
from ..services.campaigns import (filtro_campanha_vigente,
                                  parametros_vigencia, situacao_campanha)
from ..services.participants import (criar_pass_se_necessario,
                                     salvar_participacao, validar_formulario,
                                     gerar_token_participante, obter_id_por_token,
                                     quantidade_descobertas, descoberta_ja_registrada)

bp = Blueprint("public", __name__)


def _slug_amigavel(texto):
    texto = unicodedata.normalize("NFD", str(texto or ""))
    texto = "".join(char for char in texto if not unicodedata.combining(char))
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", texto.lower()).strip("-")
    return slug[:50] or "amigo"


def _pagina_convite(qr, nome_amigo, convite_url):
    jogo_da_bruxa = (qr["categoria"] or "frases") == "jogos"
    return render_template(
        "convite.html",
        qr=qr,
        nome_amigo=nome_amigo,
        jogo_da_bruxa=jogo_da_bruxa,
        convite_url=convite_url,
        imagem_compartilhamento_url=(
            BASE_URL + url_for("static", filename="images/halloween-convite.png")
        ),
    )


def _campanha_ativa():
    connection = get_connection()
    campanha = connection.execute(
        f"SELECT * FROM campanhas WHERE {filtro_campanha_vigente()} "
        "ORDER BY id DESC LIMIT 1",
        parametros_vigencia(),
    ).fetchone()
    connection.close()
    return campanha


@bp.route("/")
def index():
    """Landing completa da escola."""
    return render_template("landing.html", campanha=_campanha_ativa(), u=UNIDADE)


@bp.route("/ingles-secreto")
@bp.route("/campanha")
def campanha():
    """Página da campanha (Halloween)."""
    return render_template("campanha.html", campanha=_campanha_ativa(), u=UNIDADE)


@bp.route("/e/<codigo>")
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
            campanhas.categoria,
            campanhas.ativa,
            campanhas.data_inicio,
            campanhas.data_fim
        FROM qr_codes
        INNER JOIN campanhas ON campanhas.id = qr_codes.campanha_id
        LEFT JOIN locais ON locais.id = qr_codes.local_id
        WHERE qr_codes.codigo = ?
          AND (qr_codes.local_id IS NULL OR locais.ativo = 1)
        """,
        (codigo,),
    ).fetchone()
    connection.close()

    if not qr:
        return render_template("mensagem.html", erro="Mensagem não encontrada."), 404

    situacao = situacao_campanha(qr)
    if situacao != "ativa":
        return render_template("campanha_inativa.html", qr=qr, situacao=situacao)

    categoria = qr["categoria"] or "frases"
    desafio, historico = sortear_para_navegador(codigo, categoria)

    template_name = desafio.get("template", "desafio_halloween.html")
    response = make_response(render_template(template_name, qr=qr, desafio=desafio, codigo=codigo))
    return guardar_historico(response, historico)


@bp.route("/participar/<codigo>", methods=["GET", "POST"])
def participar(codigo):
    if request.method == "POST" and not permitir_requisicao("participacao", 60, 600):
        return make_response(
            "Muitas tentativas de cadastro. Aguarde alguns minutos e tente novamente.", 429
        )

    connection = get_connection()
    qr = connection.execute(
        f"""
        SELECT
            qr_codes.*,
            campanhas.nome AS campanha_nome,
            campanhas.semana,
            campanhas.frase,
            campanhas.traducao,
            campanhas.categoria,
            campanhas.ativa
        FROM qr_codes
        INNER JOIN campanhas ON campanhas.id = qr_codes.campanha_id
        INNER JOIN locais ON locais.id = qr_codes.local_id
        WHERE qr_codes.codigo = ? AND {filtro_campanha_vigente()} AND locais.ativo = 1
        """,
        (codigo, *parametros_vigencia()),
    ).fetchone()

    if not qr:
        connection.close()
        return render_template("mensagem.html", erro="Mensagem não encontrada."), 404

    if not session.get(f"desafio_acertado_{codigo}"):
        connection.close()
        flash("Acerte o desafio antes de liberar seu cadastro.", "error")
        return redirect(url_for("public.mensagem", codigo=codigo))

    token_cookie = request.cookies.get("knn_lead_token")
    user_id_cookie = obter_id_por_token(token_cookie)
    participante_reconhecido = None
    ja_encontrou_este_qr = False

    if user_id_cookie:
        participante_reconhecido = connection.execute(
            "SELECT id, nome, whatsapp, email, idade FROM usuarios WHERE id = ?",
            (user_id_cookie,),
        ).fetchone()

        if participante_reconhecido:
            # A mesma pessoa só contabiliza cada QR Code uma vez, em qualquer local.
            ja_encontrou_este_qr = descoberta_ja_registrada(
                connection, participante_reconhecido["id"], qr["id"]
            )

    if request.method != "POST":
        connection.close()
        return render_template(
            "participar.html",
            qr=qr,
            participante=participante_reconhecido,
            ja_encontrou=ja_encontrou_este_qr,
        )

    # Verifica se enviou o form completo OU se confirmou identificação rápida
    confirmou_reconhecido = request.form.get("confirmar_reconhecido") == "1"

    if confirmou_reconhecido and participante_reconhecido:
        nome = participante_reconhecido["nome"]
        whatsapp = participante_reconhecido["whatsapp"]
        email = participante_reconhecido["email"]
        idade = participante_reconhecido["idade"]
    else:
        nome = request.form.get("nome", "").strip()
        whatsapp = request.form.get("whatsapp", "").strip()
        email = request.form.get("email", "").strip()
        idade = request.form.get("idade", "").strip()
        confirmou = request.form.get("participacao_confirmada")

        if not (nome and whatsapp and email and idade and confirmou):
            connection.close()
            flash("Preencha os campos obrigatórios e confirme sua participação e "
                  "autorização de contato para continuar.", "error")
            return render_template("participar.html", qr=qr, participante=participante_reconhecido, ja_encontrou=ja_encontrou_este_qr)

        idade, erro = validar_formulario(nome, whatsapp, email, idade)
        if erro:
            connection.close()
            flash(erro, "error")
            return render_template("participar.html", qr=qr, participante=participante_reconhecido, ja_encontrou=ja_encontrou_este_qr)

    try:
        usuario_id, novo_registro = salvar_participacao(connection, qr, nome, whatsapp, email, idade)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    criar_pass_se_necessario(usuario_id)

    total_descobertas = quantidade_descobertas(usuario_id)

    # Prepara resposta redirecionando para /conquista
    session["contato_autorizado"] = True
    session["descobertas_usuario"] = total_descobertas
    session["nome_usuario"] = nome.split()[0] if nome else ""
    session["novo_registro"] = novo_registro
    session["categoria_conquista"] = qr["categoria"] or "frases"

    resp = make_response(redirect(url_for("public.conquista")))
    novo_token = gerar_token_participante(usuario_id)
    resp.set_cookie(
        "knn_lead_token",
        novo_token,
        max_age=86400 * 365,  # 1 ano
        httponly=True,
        samesite="Lax",
        secure=request.is_secure,
    )
    return resp


@bp.route("/e/<codigo>/redefinir", methods=["POST"])
def redefinir_participante(codigo):
    """Limpa a identificação do participante deste navegador para permitir novo cadastro."""
    resp = make_response(redirect(url_for("public.participar", codigo=codigo)))
    resp.delete_cookie("knn_lead_token")
    return resp


@bp.route("/e/<codigo>/responder", methods=["POST"])
def responder_desafio(codigo):
    if not permitir_requisicao("desafio", 120, 300):
        response = jsonify({"ok": False, "mensagem": "Muitas tentativas. Aguarde e tente novamente."})
        response.status_code = 429
        response.headers["Retry-After"] = "300"
        return response

    desafio_id = session.get(f"desafio_sorteado_{codigo}")
    if not desafio_id:
        return jsonify({"ok": False, "mensagem": "Este desafio não está disponível."}), 404

    connection = get_connection()
    qr = connection.execute(
        f"""
        SELECT campanhas.categoria
        FROM qr_codes
        INNER JOIN campanhas ON campanhas.id = qr_codes.campanha_id
        INNER JOIN locais ON locais.id = qr_codes.local_id
        WHERE qr_codes.codigo = ? AND {filtro_campanha_vigente()} AND locais.ativo = 1
        """,
        (codigo, *parametros_vigencia()),
    ).fetchone()
    connection.close()

    if not qr:
        return jsonify({"ok": False, "mensagem": "Este desafio não está disponível."}), 404

    desafio = obter_desafio_por_id(desafio_id, qr["categoria"] or "frases")
    if not desafio:
        return jsonify({"ok": False, "mensagem": "Desafio não encontrado."}), 404

    letra = request.form.get("resposta", "").strip().upper()
    if letra == desafio["resposta_correta"]:
        session[f"desafio_acertado_{codigo}"] = True
        return jsonify({"ok": True, "url": url_for("public.participar", codigo=codigo)})

    return jsonify({"ok": False, "mensagem": "Não foi dessa vez! Tente outra alternativa. 👻"})


@bp.route("/conquista")
def conquista():
    contato_autorizado = bool(session.pop("contato_autorizado", False))
    descobertas = session.pop("descobertas_usuario", 1)
    nome = session.pop("nome_usuario", "")
    novo_registro = session.pop("novo_registro", True)
    categoria = session.pop("categoria_conquista", "frases")
    session.pop("local_nome", None)
    jogo = "descubraingrediente" if categoria == "jogos" else "descubrafrase"
    slug_nome = _slug_amigavel(nome or "amigo")
    convite_url = f"{BASE_URL}{url_for('public.desafio_convite', nome=slug_nome, jogo=jogo)}"
    return render_template(
        "conquista.html",
        nome=nome,
        descobertas=descobertas,
        convite_url=convite_url,
        pass_required=ENGLISH_PASS_REQUIRED,
        contato_autorizado=contato_autorizado,
        novo_registro=novo_registro,
        instagram_url=UNIDADE.get("instagram", "https://www.instagram.com/knnparaisopolis/"),
    )


@bp.route("/desafio/<nome>/<jogo>")
def desafio_convite(nome, jogo):
    """Resolve o link amigável para o QR ativo da modalidade convidada."""
    categorias = {
        "descubrafrase": "frases",
        "descubraingrediente": "jogos",
    }
    categoria = categorias.get(jogo)
    if not categoria:
        return render_template("mensagem.html", erro="Desafio não encontrado."), 404

    connection = get_connection()
    qr = connection.execute(
        f"""
        SELECT
            qr_codes.codigo,
            campanhas.nome AS campanha_nome,
            campanhas.semana,
            campanhas.frase,
            campanhas.traducao,
            campanhas.categoria,
            campanhas.ativa,
            campanhas.data_inicio,
            campanhas.data_fim
        FROM qr_codes
        INNER JOIN campanhas ON campanhas.id = qr_codes.campanha_id
        INNER JOIN locais ON locais.id = qr_codes.local_id
        WHERE campanhas.categoria = ?
          AND {filtro_campanha_vigente()}
          AND locais.ativo = 1
        ORDER BY campanhas.id DESC, qr_codes.id DESC
        LIMIT 1
        """,
        (categoria, *parametros_vigencia()),
    ).fetchone()
    connection.close()

    if not qr:
        return render_template("mensagem.html", erro="Desafio não encontrado."), 404

    slug_nome = _slug_amigavel(nome)
    nome_amigo = slug_nome.replace("-", " ").title()
    convite_url = f"{BASE_URL}{url_for('public.desafio_convite', nome=slug_nome, jogo=jogo)}"
    return _pagina_convite(qr, nome_amigo, convite_url)


@bp.route("/convite/<codigo>")
def convite(codigo):
    """Mantém compatibilidade com convites antigos que carregam um QR específico."""
    connection = get_connection()
    qr = connection.execute(
        """
        SELECT qr_codes.codigo, campanhas.nome AS campanha_nome, campanhas.semana,
               campanhas.frase, campanhas.traducao, campanhas.categoria,
               campanhas.ativa, campanhas.data_inicio, campanhas.data_fim
        FROM qr_codes
        INNER JOIN campanhas ON campanhas.id = qr_codes.campanha_id
        LEFT JOIN locais ON locais.id = qr_codes.local_id
        WHERE qr_codes.codigo = ?
          AND (qr_codes.local_id IS NULL OR locais.ativo = 1)
        """,
        (codigo,),
    ).fetchone()
    connection.close()

    if not qr:
        return render_template("mensagem.html", erro="Desafio não encontrado."), 404

    situacao = situacao_campanha(qr)
    if situacao != "ativa":
        return render_template("campanha_inativa.html", qr=qr, situacao=situacao)

    nome_amigo = " ".join(request.args.get("de", "").split())[:50] or "Alguém"
    convite_url = f"{BASE_URL}{url_for('public.convite', codigo=codigo, de=nome_amigo)}"
    return _pagina_convite(qr, nome_amigo, convite_url)


@bp.route("/nada")
def nada():
    """Redirecionamento mantido para compatibilidade."""
    return redirect(url_for("public.conquista"))
