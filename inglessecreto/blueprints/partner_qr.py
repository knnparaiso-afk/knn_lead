import io

import qrcode
from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for

from config import BASE_URL
from database import get_connection
from ..decorators import admin_required
from ..security import permitir_requisicao
from ..services.campaigns import gerar_codigo

bp = Blueprint("partner_qr", __name__)


@bp.route("/admin/qr-avulso", methods=["GET", "POST"])
@admin_required
def lista_qrs():
    if request.method == "POST":
        if not permitir_requisicao("criar_qr_avulso", 30, 600):
            flash("Muitas solicitações. Aguarde e tente novamente.", "error")
            return redirect(url_for("partner_qr.lista_qrs"))
        parceiro = " ".join(request.form.get("parceiro", "").split())
        if not parceiro or len(parceiro) > 150:
            flash("Informe o nome do parceiro (até 150 caracteres).", "error")
            return redirect(url_for("partner_qr.lista_qrs"))
        codigo = gerar_codigo()
        connection = get_connection()
        try:
            connection.execute(
                "INSERT INTO qrs_avulsos (codigo, parceiro) VALUES (?, ?)",
                (codigo, parceiro),
            )
            connection.commit()
        finally:
            connection.close()
        flash("QR avulso criado. O link abre direto no cadastro.", "success")
        return redirect(url_for("partner_qr.lista_qrs"))

    connection = get_connection()
    qrs = connection.execute(
        """SELECT q.id, q.codigo, q.parceiro, q.data_criacao, q.ativo,
                  COUNT(c.id) AS total_cadastros
           FROM qrs_avulsos q
           LEFT JOIN cadastros_qr_avulso c ON c.qr_avulso_id = q.id
           GROUP BY q.id ORDER BY q.id DESC"""
    ).fetchall()
    connection.close()
    return render_template("admin/qr_avulso.html", qrs=qrs, base_url=BASE_URL)


@bp.route("/admin/qr-avulso/<int:qr_id>/imagem")
@admin_required
def imagem_qr(qr_id):
    connection = get_connection()
    qr = connection.execute("SELECT codigo FROM qrs_avulsos WHERE id = ?", (qr_id,)).fetchone()
    connection.close()
    if not qr:
        abort(404)
    image = qrcode.make(f"{BASE_URL}/cadastro-parceiro/{qr['codigo']}")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return send_file(buffer, mimetype="image/png", as_attachment=True,
                     download_name=f"qr-parceiro-{qr['codigo']}.png")


@bp.route("/admin/cadastros-parceiros")
@admin_required
def cadastros():
    connection = get_connection()
    registros = connection.execute(
        """SELECT c.data_cadastro, u.nome, u.whatsapp, u.email, u.idade,
                  q.parceiro, q.codigo
           FROM cadastros_qr_avulso c
           JOIN usuarios u ON u.id = c.usuario_id
           JOIN qrs_avulsos q ON q.id = c.qr_avulso_id
           ORDER BY c.data_cadastro DESC, c.id DESC"""
    ).fetchall()
    connection.close()
    return render_template("admin/cadastros_parceiros.html", registros=registros)
