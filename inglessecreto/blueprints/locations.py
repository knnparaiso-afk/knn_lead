from flask import Blueprint, flash, redirect, render_template, request, url_for

from database import get_connection

from ..decorators import admin_required
from ..services.qr_art import remover_arquivos_qr

bp = Blueprint("locations", __name__)


@bp.route("/admin/locais")
@admin_required
def locais():
    connection = get_connection()
    lista = connection.execute(
        """
        SELECT locais.*, COUNT(qr_codes.id) AS total_qr
        FROM locais
        LEFT JOIN qr_codes ON qr_codes.local_id = locais.id
        GROUP BY locais.id
        ORDER BY locais.nome
        """
    ).fetchall()
    connection.close()
    return render_template("admin/locais.html", locais=lista)


@bp.route("/admin/locais/novo", methods=["GET", "POST"])
@admin_required
def novo_local():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        endereco = request.form.get("endereco", "").strip()
        parceiro = request.form.get("parceiro", "").strip()

        if not nome or len(nome) > 120 or len(endereco) > 250 or len(parceiro) > 150:
            flash("Informe o nome do local e respeite os limites dos campos.", "error")
            return render_template("admin/local_form.html", local=None)

        connection = get_connection()
        connection.execute(
            "INSERT INTO locais (nome, endereco, parceiro) VALUES (?, ?, ?)",
            (nome, endereco, parceiro),
        )
        connection.commit()
        connection.close()

        flash("Local cadastrado!", "success")
        return redirect(url_for("locations.locais"))

    return render_template("admin/local_form.html", local=None)


@bp.route("/admin/locais/<int:local_id>/excluir", methods=["POST"])
@admin_required
def excluir_local(local_id):
    connection = get_connection()
    qrs = connection.execute(
        "SELECT codigo FROM qr_codes WHERE local_id = ?", (local_id,)
    ).fetchall()
    local = connection.execute(
        "SELECT id FROM locais WHERE id = ?", (local_id,)
    ).fetchone()

    if not local:
        connection.close()
        flash("Local não encontrado.", "error")
        return redirect(url_for("locations.locais"))

    connection.execute("DELETE FROM locais WHERE id = ?", (local_id,))
    connection.commit()
    connection.close()

    remover_arquivos_qr(qr["codigo"] for qr in qrs)
    flash("Local e seus QR Codes foram excluídos.", "success")
    return redirect(url_for("locations.locais"))
