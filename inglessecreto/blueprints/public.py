import re
import unicodedata
from urllib.parse import urlencode, urlsplit

from flask import (Blueprint, flash, jsonify, make_response, redirect,
                   render_template, request, session, url_for)

from database import get_connection
from desafios import obter_desafio_por_id
from telefones import normalizar_whatsapp

from config import BASE_URL, BIO_COMUNIDADE_URL, ENGLISH_PASS_REQUIRED, UNIDADE
from ..reviews import GOOGLE_REVIEWS
from ..security import permitir_requisicao
from ..utils import hoje_brasilia
from ..services.challenges import guardar_historico, sortear_para_navegador
from ..services.qr_metrics import registrar_evento_qr_avulso
from ..services.campaigns import (CADASTRO_DIRETO, cadastro_direto, filtro_campanha_vigente,
                                  parametros_vigencia, situacao_campanha, periodo_campanha)
from ..services.participants import (criar_pass_se_necessario,
                                     salvar_participacao, validar_formulario,
                                     gerar_token_participante, obter_id_por_token,
                                     quantidade_descobertas, descoberta_ja_registrada,
                                     obter_progresso_por_whatsapp,
                                     DIRECT_REGISTRATION_CONSENT_TEXT, salvar_cadastro_direto)

bp = Blueprint("public", __name__)

METRIC_EVENTS = {
    "qr_open", "challenge_start", "challenge_complete", "reward_view", "form_start",
    "form_complete", "whatsapp_click", "friend_share_click",
    "friend_invite_open", "friend_invite_accept",
}


def _registrar_metrica(connection, evento, qr_code_id=0, campanha_id=0,
                       categoria="", origem="qr"):
    if evento not in METRIC_EVENTS:
        return
    hoje = hoje_brasilia().isoformat()
    connection.execute(
        """
        INSERT INTO metricas_funil
            (data, evento, qr_code_id, campanha_id, categoria, origem, total)
        VALUES (?, ?, ?, ?, ?, ?, 1)
        ON CONFLICT(data, evento, qr_code_id, campanha_id, categoria, origem)
        DO UPDATE SET total = metricas_funil.total + 1
        """,
        (hoje, evento, qr_code_id or 0, campanha_id or 0, categoria or "", origem or "qr"),
    )


def _registrar_metrica_da_sessao(evento):
    qr_code_id = session.get("metric_qr_id", 0)
    campanha_id = session.get("metric_campaign_id", 0)
    categoria = session.get("metric_category", "")
    origem = session.get("metric_origin", "qr")
    connection = get_connection()
    try:
        _registrar_metrica(connection, evento, qr_code_id, campanha_id, categoria, origem)
        connection.commit()
    finally:
        connection.close()


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


def _campanha_ativa(so_desafios=False):
    connection = get_connection()
    campanha = connection.execute(
        f"SELECT * FROM campanhas WHERE {filtro_campanha_vigente()} "
        + ("AND categoria IN ('frases', 'jogos') " if so_desafios else "AND exibir_faixa = 1 ")
        + "ORDER BY id DESC LIMIT 1",
        parametros_vigencia(),
    ).fetchone()
    connection.close()
    return campanha


def _comunidade_local_url(campanha):
    """Reutiliza o convite permanente da bio quando a campanha não tem um próprio."""
    link = (campanha["comunidade_url"] if campanha else "") or BIO_COMUNIDADE_URL
    try:
        destino = urlsplit(link)
    except ValueError:
        return ""
    return link if destino.scheme == "https" and destino.netloc else ""


@bp.route("/")
def index():
    """Landing completa da escola."""
    campanha = _campanha_ativa()
    return render_template("landing.html", campanha=campanha, u=UNIDADE, reviews=GOOGLE_REVIEWS,
                           comunidade_local_url=_comunidade_local_url(campanha),
                           periodo=periodo_campanha(campanha) if cadastro_direto(campanha) else None)


@bp.route("/bio")
def bio():
    """Página permanente de links da unidade, sem depender de campanhas."""
    whatsapp_url = "https://wa.me/" + UNIDADE["whatsapp"]
    aula_url = whatsapp_url + "?" + urlencode({
        "text": "Olá! Vim pelo link da bio da KNN Paraisópolis e quero agendar minha aula grátis."
    })
    comunidade_url = BIO_COMUNIDADE_URL
    destino = urlsplit(comunidade_url)
    comunidade_direta = destino.scheme == "https" and bool(destino.netloc)
    if not comunidade_direta:
        comunidade_url = whatsapp_url + "?" + urlencode({
            "text": "Olá! Quero o link da comunidade KNN Paraisópolis."
        })
    return render_template(
        "bio.html", u=UNIDADE, aula_url=aula_url,
        comunidade_url=comunidade_url, comunidade_direta=comunidade_direta,
        canonical_url=BASE_URL + url_for("public.bio"),
        imagem_url=BASE_URL + url_for("static", filename="img/black-november-knn.jpeg"),
    )


@bp.route("/bio/")
@bp.route("/links")
@bp.route("/links/")
def bio_alias():
    return redirect(url_for("public.bio"), code=308)


@bp.route("/ingles-secreto")
@bp.route("/campanha")
def campanha():
    """Página da campanha (Halloween)."""
    return render_template("campanha.html", campanha=_campanha_ativa(so_desafios=True), u=UNIDADE)


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

    origem = "amigo" if request.args.get("indicado") == "1" else "qr"
    session["metric_qr_id"] = qr["id"]
    session["metric_campaign_id"] = qr["campanha_id"]
    session["metric_category"] = qr["categoria"] or "frases"
    session["metric_origin"] = origem
    connection = get_connection()
    _registrar_metrica(connection, "qr_open", qr["id"], qr["campanha_id"],
                       qr["categoria"] or "frases", origem)
    if origem == "amigo":
        _registrar_metrica(connection, "friend_invite_accept", qr["id"], qr["campanha_id"],
                           qr["categoria"] or "frases", origem)
    connection.commit()
    connection.close()

    categoria = qr["categoria"] or "frases"
    desafio, historico = sortear_para_navegador(codigo, categoria)

    template_name = desafio.get("template", "desafio_halloween.html")
    response = make_response(render_template(template_name, qr=qr, desafio=desafio, codigo=codigo))
    return guardar_historico(response, historico)


def _recompensa_prevista(participante, ja_encontrou):
    atual = quantidade_descobertas(participante["id"]) if participante else 0
    total = atual + int(not ja_encontrou)
    if total >= ENGLISH_PASS_REQUIRED:
        titulo = "English Pass"
        descricao = ("50% de desconto e isenção na taxa de matrícula, com pagamento "
                     "após um mês do início dos estudos.")
        icone = "🏆"
    elif total >= 2:
        titulo = "Aula gratuita com certificado"
        descricao = "Uma experiência de inglês na KNN, com certificado. Retire o acesso em nossa escola."
        icone = "🎓"
    else:
        titulo = "Combo KNN"
        descricao = "Seu combo para retirar em nossa escola."
        icone = "🎁"
    return {"titulo": titulo, "descricao": descricao, "icone": icone,
            "total": total, "maximo_anterior": atual >= ENGLISH_PASS_REQUIRED}


@bp.route("/recompensa/<codigo>")
def recompensa(codigo):
    return participar(codigo, mostrar_recompensa=True)


@bp.route("/participar/<codigo>", methods=["GET", "POST"])
def participar(codigo, mostrar_recompensa=False):
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
        flash("Acerte o desafio antes de ver seu prêmio.", "error")
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

    vistas = session.get("recompensas_vistas", [])
    if request.method == "GET" and not mostrar_recompensa and codigo not in vistas:
        connection.close()
        return redirect(url_for("public.recompensa", codigo=codigo))

    # A consulta por celular informa o prêmio, mas nunca libera confirmação
    # rápida nem preenche dados pessoais de outro navegador.
    participante_progresso = participante_reconhecido
    if request.method == "POST" and request.form.get("confirmar_reconhecido") != "1":
        celular = normalizar_whatsapp(request.form.get("whatsapp", ""))
        participante_progresso = obter_progresso_por_whatsapp(connection, celular)
        # Em erros de cadastro, use a identidade enviada, não a do cookie.
        participante_reconhecido = None
    ja_encontrou_este_qr = bool(participante_progresso) and descoberta_ja_registrada(
        connection, participante_progresso["id"], qr["id"]
    )
    premio = _recompensa_prevista(participante_progresso, ja_encontrou_este_qr)
    premio["historico_conferido"] = bool(participante_progresso)
    premio["ja_encontrou"] = ja_encontrou_este_qr
    if not mostrar_recompensa and request.form.get("consultar_premio") == "1":
        connection.close()
        return jsonify(premio)
    if mostrar_recompensa:
        # A tela de prévia não usa o cookie como identidade. Mostra o prêmio
        # da primeira descoberta; o cadastro consulta o histórico pelo celular.
        premio = _recompensa_prevista(None, False)
        premio["historico_conferido"] = False
        premio["ja_encontrou"] = False
        session["recompensas_vistas"] = [c for c in vistas if c != codigo][-7:] + [codigo]
        _registrar_metrica(connection, "reward_view", qr["id"], qr["campanha_id"],
                           qr["categoria"] or "frases", session.get("metric_origin", "qr"))
        connection.commit()
        connection.close()
        return render_template("recompensa.html", qr=qr, premio=premio,
                               participante=None, ja_encontrou=False)

    if request.method != "POST":
        _registrar_metrica(connection, "form_start", qr["id"], qr["campanha_id"],
                           qr["categoria"] or "frases", session.get("metric_origin", "qr"))
        connection.commit()
        connection.close()
        return render_template(
            "participar.html",
            qr=qr,
            participante=participante_reconhecido,
            ja_encontrou=ja_encontrou_este_qr,
            premio=premio,
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
            return render_template("participar.html", qr=qr, participante=participante_reconhecido, ja_encontrou=ja_encontrou_este_qr, premio=premio)

        idade, erro = validar_formulario(nome, whatsapp, email, idade)
        if erro:
            connection.close()
            flash(erro, "error")
            return render_template("participar.html", qr=qr, participante=participante_reconhecido, ja_encontrou=ja_encontrou_este_qr, premio=premio)

    try:
        usuario_id, novo_registro = salvar_participacao(connection, qr, nome, whatsapp, email, idade)
        _registrar_metrica(
            connection, "form_complete", qr["id"], qr["campanha_id"],
            qr["categoria"] or "frases", session.get("metric_origin", "qr"),
        )
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


@bp.route("/cadastro-parceiro/<codigo>", methods=["GET", "POST"])
def cadastro_parceiro(codigo):
    """Entrada estável dos QR impressos, vinculados ou ainda independentes."""
    if request.method == "POST" and not permitir_requisicao("cadastro_parceiro", 30, 600):
        return make_response("Muitas tentativas de cadastro. Aguarde alguns minutos e tente novamente.", 429)
    connection = get_connection()
    qr = connection.execute(
        "SELECT id, codigo, parceiro, campanha_id, origem FROM qrs_avulsos WHERE codigo = ? AND ativo = 1",
        (codigo,),
    ).fetchone()
    if not qr:
        connection.close()
        return render_template("mensagem.html", erro="Este cadastro não está disponível."), 404
    campanha = None
    if qr["campanha_id"]:
        campanha = connection.execute("SELECT * FROM campanhas WHERE id = ?", (qr["campanha_id"],)).fetchone()
        if not cadastro_direto(campanha) or situacao_campanha(campanha) != "ativa":
            connection.close()
            return render_template("black_indisponivel.html"), 404

    def formulario():
        return render_template(
            "cadastro_parceiro.html",
            consentimento=DIRECT_REGISTRATION_CONSENT_TEXT,
            campanha=campanha,
        )

    def registrar_e_fechar(evento):
        try:
            registrar_evento_qr_avulso(connection, qr["id"], evento)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    if request.method in ("GET", "HEAD"):
        if request.method == "GET":
            registrar_e_fechar("acesso")
        else:
            connection.close()
        return formulario()

    nome = request.form.get("nome", "").strip()
    whatsapp = request.form.get("whatsapp", "").strip()
    email = request.form.get("email", "").strip()
    idade_str = request.form.get("idade", "").strip()
    if not (nome and whatsapp and email and idade_str and request.form.get("participacao_confirmada")):
        registrar_e_fechar("erro_validacao")
        flash("Preencha os campos obrigatórios e confirme a autorização de contato.", "error")
        return formulario(), 400
    idade, erro = validar_formulario(nome, whatsapp, email, idade_str)
    if erro:
        registrar_e_fechar("erro_validacao")
        flash(erro, "error")
        return formulario(), 400
    whatsapp = normalizar_whatsapp(whatsapp)
    try:
        salvar_cadastro_direto(connection, qr, nome, whatsapp, email, idade)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    session["cadastro_direto_qr_id"] = qr["id"]
    return redirect(url_for("public.cadastro_parceiro_concluido"))


@bp.route("/cadastro/<codigo>", methods=["GET", "POST"])
def cadastro_campanha(codigo):
    connection = get_connection()
    try:
        qr = connection.execute(
            "SELECT q.codigo FROM qrs_avulsos q JOIN campanhas c ON c.id = q.campanha_id "
            "WHERE c.codigo = ? AND c.categoria = ? AND q.ativo = 1 AND q.origem = 'landing' LIMIT 1",
            (codigo, CADASTRO_DIRETO),
        ).fetchone()
    finally:
        connection.close()
    if not qr:
        return render_template("black_indisponivel.html"), 404
    return cadastro_parceiro(qr["codigo"])


@bp.route("/black-november/<codigo>", methods=["GET", "POST"])
def cadastro_black(codigo):
    """Compatibilidade com links já divulgados; mantém inclusive POST e CSRF."""
    return cadastro_campanha(codigo)


@bp.route("/cadastro-parceiro/concluido")
def cadastro_parceiro_concluido():
    session.pop("cadastro_parceiro_concluido", None)
    qr_id = session.get("cadastro_direto_qr_id")
    if not qr_id:
        return redirect(url_for("public.index"))
    connection = get_connection()
    try:
        qr = connection.execute("SELECT campanha_id FROM qrs_avulsos WHERE id = ?", (qr_id,)).fetchone()
        if not qr:
            return redirect(url_for("public.index"))
        campanha = (connection.execute("SELECT * FROM campanhas WHERE id = ?", (qr["campanha_id"],)).fetchone()
                    if qr["campanha_id"] else None)
    finally:
        connection.close()
    if campanha and (not cadastro_direto(campanha) or situacao_campanha(campanha) != "ativa"):
        campanha = None
    whatsapp_url = "https://wa.me/" + UNIDADE["whatsapp"] + "?" + urlencode({
        "text": "Olá! Fiz meu cadastro na Black November da KNN Paraisópolis e quero conhecer os cursos e as condições dos benefícios."
    })
    return render_template("cadastro_parceiro_concluido.html", campanha=campanha, u=UNIDADE,
                           whatsapp_url=whatsapp_url, comunidade_local_url=_comunidade_local_url(campanha))


@bp.route("/e/<codigo>/redefinir", methods=["POST"])
def redefinir_participante(codigo):
    """Limpa a identificação do participante deste navegador para permitir novo cadastro."""
    session["recompensas_vistas"] = [c for c in session.get("recompensas_vistas", []) if c != codigo]
    resp = make_response(redirect(url_for("public.recompensa", codigo=codigo)))
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
    categoria = qr["categoria"] or "frases"
    if categoria == "jogos" and letra == "GAME_COMPLETE":
        session[f"desafio_acertado_{codigo}"] = True
        _registrar_metrica_da_sessao("challenge_complete")
        return jsonify({"ok": True, "url": url_for("public.recompensa", codigo=codigo)})

    if letra == desafio["resposta_correta"]:
        session[f"desafio_acertado_{codigo}"] = True
        _registrar_metrica_da_sessao("challenge_complete")
        return jsonify({"ok": True, "url": url_for("public.recompensa", codigo=codigo)})

    return jsonify({"ok": False, "mensagem": "Não foi dessa vez! Tente outra alternativa. 👻"})


@bp.route("/conquista")
def conquista():
    if session.pop("cadastro_parceiro_concluido", False):
        return redirect(url_for("public.index"))
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
            qr_codes.id,
            qr_codes.codigo,
            qr_codes.campanha_id,
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

    session["metric_qr_id"] = qr["id"]
    session["metric_campaign_id"] = qr["campanha_id"]
    session["metric_category"] = qr["categoria"] or "frases"
    session["metric_origin"] = "amigo"
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
        SELECT qr_codes.id, qr_codes.campanha_id, qr_codes.codigo, campanhas.nome AS campanha_nome, campanhas.semana,
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

    session["metric_origin"] = "amigo"
    session["metric_qr_id"] = qr["id"]
    session["metric_campaign_id"] = qr["campanha_id"]
    session["metric_category"] = qr["categoria"] or "frases"

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


@bp.route("/metricas/evento", methods=["POST"])
def registrar_evento_metrica():
    data = request.get_json(silent=True) or {}
    evento = data.get("evento")
    if evento not in {
        "challenge_start", "whatsapp_click", "friend_share_click", "friend_invite_open",
    }:
        return jsonify({"ok": False}), 400
    _registrar_metrica_da_sessao(evento)
    return jsonify({"ok": True})
