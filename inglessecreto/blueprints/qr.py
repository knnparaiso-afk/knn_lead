import os

from flask import (Blueprint, flash, make_response, redirect,
                   render_template, request, send_file, url_for)

from config import BASE_URL, QR_LOCAL_GENERICO
from database import get_connection

from ..decorators import admin_required
from ..security import permitir_requisicao
from ..services.campaigns import gerar_codigo
from ..services.qr_art import (ARTE_QR_PADRAO, artes_qr_disponiveis,
                               caminho_qr, gerar_arte_qrcode,
                               normalizar_arte_qr, normalizar_tamanho_papel,
                               remover_arquivos_qr, TAMANHOS_PAPEL)

bp = Blueprint("qr", __name__)

_QR_COM_CAMPANHA_E_LOCAL = """
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
"""


def _buscar_qr(codigo):
    connection = get_connection()
    try:
        return connection.execute(_QR_COM_CAMPANHA_E_LOCAL, (codigo,)).fetchone()
    finally:
        connection.close()


def _arte_do_qr(qr, arte=ARTE_QR_PADRAO, tamanho="a4"):
    return gerar_arte_qrcode(qr["codigo"], arte, tamanho)


def _nome_download(campanha_nome, local_nome, codigo, arte=ARTE_QR_PADRAO, tamanho="a4"):
    import re, unicodedata
    def slug(t):
        if not t: return "geral"
        texto = unicodedata.normalize("NFD", str(t).lower())
        texto = "".join(c for c in texto if not unicodedata.combining(c))
        return re.sub(r"[^a-z0-9]+", "-", texto).strip("-")
    c_slug = slug(campanha_nome)
    l_slug = slug(local_nome)
    sufixo_tamanho = "-a5" if tamanho == "a5" else ""
    return f"qr-{c_slug}-{l_slug}-{codigo}-{arte}{sufixo_tamanho}.png"


@bp.route("/admin/qr/<int:campanha_id>")
@admin_required
def gerenciar_qr(campanha_id):
    connection = get_connection()
    campanha = connection.execute(
        "SELECT * FROM campanhas WHERE id = ?", (campanha_id,)
    ).fetchone()
    locais = connection.execute(
        "SELECT * FROM locais WHERE ativo = 1 AND nome = ? ORDER BY id LIMIT 1",
        (QR_LOCAL_GENERICO,),
    ).fetchall()
    qrs = connection.execute(
        """
        SELECT qr_codes.*
        FROM qr_codes
        WHERE qr_codes.campanha_id = ?
        ORDER BY qr_codes.id DESC
        """,
        (campanha_id,),
    ).fetchall()
    total_qrs = connection.execute(
        "SELECT COUNT(*) AS total FROM qr_codes"
    ).fetchone()["total"]
    connection.close()
    return render_template(
        "admin/locais.html",
        locais=locais,
        campanha_qr=campanha,
        qrs=qrs,
        total_qrs=total_qrs,
        base_url=BASE_URL,
        local_generico=QR_LOCAL_GENERICO,
    )


@bp.route("/admin/qr/<int:campanha_id>/<int:local_id>/gerar", methods=["POST"])
@admin_required
def gerar_qr(campanha_id, local_id):
    if not permitir_requisicao("gerar_qr", 30, 600):
        return make_response("Muitas solicitações. Aguarde e tente novamente.", 429)

    connection = get_connection()
    campanha = connection.execute(
        "SELECT * FROM campanhas WHERE id = ?", (campanha_id,)
    ).fetchone()
    local = connection.execute(
        "SELECT * FROM locais WHERE id = ? AND nome = ? AND ativo = 1",
        (local_id, QR_LOCAL_GENERICO),
    ).fetchone()

    if not campanha or not local:
        connection.close()
        flash("Campanha ou local não encontrado.", "error")
        return redirect(url_for("campaigns.campanhas"))

    codigo = gerar_codigo()
    connection.execute(
        "INSERT INTO qr_codes (codigo, campanha_id, local_id) VALUES (?, ?, ?)",
        (codigo, campanha_id, local_id),
    )
    connection.commit()
    connection.close()

    return redirect(url_for("qr.imprimir_qr", codigo=codigo))


@bp.route("/admin/qr/<codigo>/download")
@admin_required
def download_qr(codigo):
    qr = _buscar_qr(codigo)
    if not qr:
        flash("QR Code não encontrado.", "error")
        return redirect(url_for("campaigns.campanhas"))
    arte = normalizar_arte_qr(request.args.get("arte"))
    tamanho = normalizar_tamanho_papel(request.args.get("tamanho"))
    return send_file(
        _arte_do_qr(qr, arte, tamanho), mimetype="image/png", as_attachment=True,
        download_name=_nome_download(qr["campanha_nome"], qr["local_nome"], codigo, arte, tamanho),
    )


@bp.route("/admin/qr/<codigo>/imagem")
@admin_required
def imagem_qr(codigo):
    qr = _buscar_qr(codigo)
    if not qr:
        return "Não encontrado", 404
    arte = normalizar_arte_qr(request.args.get("arte"))
    tamanho = normalizar_tamanho_papel(request.args.get("tamanho"))
    caminho = caminho_qr(codigo, arte, tamanho)
    if not os.path.exists(caminho):
        caminho = _arte_do_qr(qr, arte, tamanho)
    response = send_file(caminho, mimetype="image/png", max_age=3600)
    response.cache_control.public = False
    response.cache_control.private = True
    return response


@bp.route("/admin/qr/<codigo>/imprimir")
@admin_required
def imprimir_qr(codigo):
    qr = _buscar_qr(codigo)
    if not qr:
        flash("QR Code não encontrado.", "error")
        return redirect(url_for("campaigns.campanhas"))
    arte = normalizar_arte_qr(request.args.get("arte"))
    tamanho = normalizar_tamanho_papel(request.args.get("tamanho"))
    formato = TAMANHOS_PAPEL[tamanho]
    _arte_do_qr(qr, arte, tamanho)
    return render_template(
        "admin/imprimir_qr.html",
        qr=qr,
        artes=artes_qr_disponiveis(),
        arte_selecionada=arte,
        tamanho=tamanho,
        formato=formato,
        tamanhos_papel=TAMANHOS_PAPEL,
        imagem_url=url_for("qr.imagem_qr", codigo=codigo, arte=arte, tamanho=tamanho),
    )


@bp.route("/admin/qr/<int:qr_id>/excluir", methods=["POST"])
@admin_required
def excluir_qr(qr_id):
    connection = get_connection()
    qr = connection.execute(
        "SELECT codigo, campanha_id FROM qr_codes WHERE id = ?", (qr_id,)
    ).fetchone()

    if not qr:
        connection.close()
        flash("QR Code não encontrado.", "error")
        return redirect(url_for("campaigns.campanhas"))

    connection.execute("DELETE FROM qr_codes WHERE id = ?", (qr_id,))
    connection.commit()
    connection.close()

    remover_arquivos_qr([qr["codigo"]])
    flash("QR Code excluído. Você pode gerar outro para esta campanha.", "success")
    return redirect(url_for("qr.gerenciar_qr", campanha_id=qr["campanha_id"]))
