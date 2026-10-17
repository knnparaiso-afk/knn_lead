import os

from flask import (Blueprint, flash, make_response, redirect,
                   render_template, send_file, url_for)

from database import get_connection

from ..decorators import admin_required
from ..security import permitir_requisicao
from ..services.campaigns import gerar_codigo
from ..services.qr_art import caminho_qr, gerar_arte_qrcode, remover_arquivos_qr

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


def _arte_do_qr(qr):
    campanha = {"semana": qr["semana"], "frase": qr["frase"], "nome": qr["campanha_nome"]}
    local = {"nome": qr["local_nome"], "parceiro": qr["parceiro"]}
    return gerar_arte_qrcode(qr["codigo"], campanha, local)


def _nome_download(campanha_nome, local_nome, codigo):
    import re, unicodedata
    def slug(t):
        if not t: return "geral"
        texto = unicodedata.normalize("NFD", str(t).lower())
        texto = "".join(c for c in texto if not unicodedata.combining(c))
        return re.sub(r"[^a-z0-9]+", "-", texto).strip("-")
    c_slug = slug(campanha_nome)
    l_slug = slug(local_nome)
    return f"qr-{c_slug}-{l_slug}-{codigo}.png"


@bp.route("/admin/qr/<int:campanha_id>")
@admin_required
def gerenciar_qr(campanha_id):
    connection = get_connection()
    campanha = connection.execute(
        "SELECT * FROM campanhas WHERE id = ?", (campanha_id,)
    ).fetchone()
    locais = connection.execute(
        "SELECT * FROM locais WHERE ativo = 1 ORDER BY nome"
    ).fetchall()
    qrs = connection.execute(
        """
        SELECT qr_codes.*, locais.nome AS local_nome, locais.parceiro
        FROM qr_codes
        INNER JOIN locais ON locais.id = qr_codes.local_id
        WHERE qr_codes.campanha_id = ?
        ORDER BY qr_codes.id DESC
        """,
        (campanha_id,),
    ).fetchall()
    connection.close()
    return render_template("admin/locais.html", locais=locais, campanha_qr=campanha, qrs=qrs)


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
        "SELECT * FROM locais WHERE id = ?", (local_id,)
    ).fetchone()

    if not campanha or not local:
        connection.close()
        flash("Campanha ou local não encontrado.", "error")
        return redirect(url_for("campaigns.campanhas"))

    existente = connection.execute(
        "SELECT codigo FROM qr_codes WHERE campanha_id = ? AND local_id = ?",
        (campanha_id, local_id),
    ).fetchone()
    if existente:
        connection.close()
        flash("Este local já possui um QR Code para esta campanha.", "error")
        return redirect(url_for("qr.gerenciar_qr", campanha_id=campanha_id))

    codigo = gerar_codigo()
    connection.execute(
        "INSERT INTO qr_codes (codigo, campanha_id, local_id) VALUES (?, ?, ?)",
        (codigo, campanha_id, local_id),
    )
    connection.commit()
    connection.close()

    caminho = gerar_arte_qrcode(codigo, campanha, local)
    return send_file(caminho, mimetype="image/png", as_attachment=True,
                     download_name=_nome_download(campanha["nome"], local["nome"], codigo))


@bp.route("/admin/qr/<codigo>/download")
@admin_required
def download_qr(codigo):
    qr = _buscar_qr(codigo)
    if not qr:
        flash("QR Code não encontrado.", "error")
        return redirect(url_for("campaigns.campanhas"))
    return send_file(_arte_do_qr(qr), mimetype="image/png", as_attachment=True,
                     download_name=_nome_download(qr["campanha_nome"], qr["local_nome"], codigo))


@bp.route("/admin/qr/<codigo>/imagem")
@admin_required
def imagem_qr(codigo):
    qr = _buscar_qr(codigo)
    if not qr:
        return "Não encontrado", 404
    caminho = caminho_qr(codigo)
    if not os.path.exists(caminho):
        caminho = _arte_do_qr(qr)
    return send_file(caminho, mimetype="image/png")


@bp.route("/admin/qr/<codigo>/imprimir")
@admin_required
def imprimir_qr(codigo):
    qr = _buscar_qr(codigo)
    if not qr:
        flash("QR Code não encontrado.", "error")
        return redirect(url_for("campaigns.campanhas"))
    _arte_do_qr(qr)
    return render_template("admin/imprimir_qr.html", qr=qr)


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
    flash("QR Code excluído. Você pode gerar outro para este local.", "success")
    return redirect(url_for("qr.gerenciar_qr", campanha_id=qr["campanha_id"]))
