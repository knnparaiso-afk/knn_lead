from datetime import datetime

from flask import (Blueprint, flash, jsonify, make_response, redirect,
                   render_template, request, session, url_for)

from database import get_connection
from desafios import sortear_desafio, obter_desafio_por_id

from ..security import permitir_requisicao
from ..services.participants import (criar_pass_se_necessario,
                                     salvar_participacao, validar_formulario)
from ..utils import hoje_brasilia

bp = Blueprint("public", __name__)


@bp.route("/")
def index():
    connection = get_connection()
    campanha = connection.execute(
        "SELECT * FROM campanhas WHERE ativa = 1 ORDER BY id DESC LIMIT 1"
    ).fetchone()
    connection.close()
    return render_template("index.html", campanha=campanha)


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

    if request.method != "POST":
        connection.close()
        return render_template("participar.html", qr=qr)

    nome = request.form.get("nome", "").strip()
    whatsapp = request.form.get("whatsapp", "").strip()
    email = request.form.get("email", "").strip()
    idade = request.form.get("idade", "").strip()
    confirmou = request.form.get("participacao_confirmada")

    if not (nome and whatsapp and email and idade and confirmou):
        connection.close()
        flash("Preencha os campos obrigatórios e confirme sua participação e "
              "autorização de contato para continuar.", "error")
        return render_template("participar.html", qr=qr)

    idade, erro = validar_formulario(nome, whatsapp, email, idade)
    if erro:
        connection.close()
        flash(erro, "error")
        return render_template("participar.html", qr=qr)

    try:
        usuario_id = salvar_participacao(connection, qr, nome, whatsapp, email, idade)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    criar_pass_se_necessario(usuario_id)

    # Não guardar dados pessoais no cookie assinado.
    session.pop("ultimo_lead_nome", None)
    session["contato_autorizado"] = True
    return redirect(url_for("public.nada"))


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


@bp.route("/nada")
def nada():
    contato_autorizado = bool(session.pop("contato_autorizado", False))
    session.pop("ultimo_lead_nome", None)
    return render_template(
        "nada.html",
        nome="",
        contato_autorizado=contato_autorizado,
        instagram_url="https://www.instagram.com/knnparaisopolis/",
    )
