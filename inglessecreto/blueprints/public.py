from datetime import datetime

from flask import (Blueprint, flash, jsonify, make_response, redirect,
                   render_template, request, session, url_for)

from database import get_connection
from desafios import sortear_desafio, obter_desafio_por_id

from config import ENGLISH_PASS_REQUIRED, UNIDADE
from ..security import permitir_requisicao
from ..services.participants import (criar_pass_se_necessario,
                                     salvar_participacao, validar_formulario,
                                     gerar_token_participante, obter_id_por_token,
                                     quantidade_descobertas)
from ..utils import hoje_brasilia

bp = Blueprint("public", __name__)


def _campanha_ativa():
    connection = get_connection()
    campanha = connection.execute(
        "SELECT * FROM campanhas WHERE ativa = 1 ORDER BY id DESC LIMIT 1"
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
            campanhas.categoria,
            campanhas.ativa,
            campanhas.data_inicio,
            campanhas.data_fim,
            locais.nome AS local_nome,
            locais.parceiro
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

    hoje = hoje_brasilia()
    parse = lambda s: datetime.strptime(s, "%Y-%m-%d").date() if s else None
    data_inicio, data_fim = parse(qr["data_inicio"]), parse(qr["data_fim"])

    encerrada = not qr["ativa"] or (data_fim is not None and hoje > data_fim)
    ainda_nao_iniciou = data_inicio is not None and hoje < data_inicio
    if encerrada or ainda_nao_iniciou:
        return render_template("campanha_inativa.html", qr=qr)

    categoria = qr["categoria"] or "frases"
    session_key = f"desafio_sorteado_{codigo}"

    desafio = None
    desafio_id = session.get(session_key)
    if desafio_id:
        desafio = obter_desafio_por_id(desafio_id, categoria)

    if not desafio:
        desafio = sortear_desafio(categoria)
        if not desafio:
            return render_template("mensagem.html", erro="Nenhum desafio disponível."), 404
        session[session_key] = desafio["id"]

    template_name = desafio.get("template", "desafio_halloween.html")
    return render_template(template_name, qr=qr, desafio=desafio, codigo=codigo)


@bp.route("/participar/<codigo>", methods=["GET", "POST"])
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
        INNER JOIN campanhas ON campanhas.id = qr_codes.campanha_id
        INNER JOIN locais ON locais.id = qr_codes.local_id
        WHERE qr_codes.codigo = ? AND campanhas.ativa = 1 AND locais.ativo = 1
        """,
        (codigo,),
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
    ja_encontrou_este_local = False

    if user_id_cookie:
        participante_reconhecido = connection.execute(
            "SELECT id, nome, whatsapp, email, idade FROM usuarios WHERE id = ?",
            (user_id_cookie,),
        ).fetchone()

        if participante_reconhecido:
            # Verifica se já encontrou o QR Code deste local
            descoberta_existente = connection.execute(
                "SELECT id FROM descobertas WHERE usuario_id = ? AND qr_code_id = ?",
                (participante_reconhecido["id"], qr["id"]),
            ).fetchone()
            if descoberta_existente:
                ja_encontrou_este_local = True

    if request.method != "POST":
        connection.close()
        return render_template(
            "participar.html",
            qr=qr,
            participante=participante_reconhecido,
            ja_encontrou=ja_encontrou_este_local,
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
            return render_template("participar.html", qr=qr, participante=participante_reconhecido, ja_encontrou=ja_encontrou_este_local)

        idade, erro = validar_formulario(nome, whatsapp, email, idade)
        if erro:
            connection.close()
            flash(erro, "error")
            return render_template("participar.html", qr=qr, participante=participante_reconhecido, ja_encontrou=ja_encontrou_este_local)

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
    session["local_nome"] = qr["local_nome"]

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
        """
        SELECT campanhas.categoria
        FROM qr_codes
        INNER JOIN campanhas ON campanhas.id = qr_codes.campanha_id
        INNER JOIN locais ON locais.id = qr_codes.local_id
        WHERE qr_codes.codigo = ? AND campanhas.ativa = 1 AND locais.ativo = 1
        """,
        (codigo,),
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
    local_nome = session.pop("local_nome", "")
    return render_template(
        "conquista.html",
        nome=nome,
        descobertas=descobertas,
        pass_required=ENGLISH_PASS_REQUIRED,
        contato_autorizado=contato_autorizado,
        novo_registro=novo_registro,
        local_nome=local_nome,
        instagram_url=UNIDADE.get("instagram", "https://www.instagram.com/knnparaisopolis/"),
    )


@bp.route("/nada")
def nada():
    """Redirecionamento mantido para compatibilidade."""
    return redirect(url_for("public.conquista"))
