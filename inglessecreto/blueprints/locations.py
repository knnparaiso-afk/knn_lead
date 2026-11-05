from flask import Blueprint, flash, redirect, render_template, url_for

from database import get_connection

from ..decorators import admin_required
from ..services.campaigns import situacao_campanha

bp = Blueprint("locations", __name__)


@bp.route("/admin/locais")
@admin_required
def locais():
    connection = get_connection()
    try:
        campanhas = connection.execute(
            """
            SELECT campanhas.*,
                   (SELECT COUNT(*) FROM qr_codes
                    WHERE qr_codes.campanha_id = campanhas.id) +
                   (SELECT COUNT(*) FROM qrs_avulsos WHERE qrs_avulsos.campanha_id = campanhas.id AND qrs_avulsos.origem = 'qr') AS total_qrs
            FROM campanhas
            ORDER BY campanhas.id DESC
            """
        ).fetchall()
    finally:
        connection.close()
    situacoes = {campanha["id"]: situacao_campanha(campanha) for campanha in campanhas}
    return render_template(
        "admin/qr_campaigns.html",
        campanhas=campanhas,
        situacoes=situacoes,
    )


@bp.route("/admin/locais/novo", methods=["GET", "POST"])
@admin_required
def novo_local():
    flash(
        "O cadastro por estabelecimento foi encerrado. Os QR Codes usam um ponto geral.",
        "info",
    )
    return redirect(url_for("locations.locais"))


@bp.route("/admin/locais/<int:local_id>/excluir", methods=["POST"])
@admin_required
def excluir_local(local_id):
    connection = get_connection()
    existe = connection.execute(
        "SELECT id FROM locais WHERE id = ?", (local_id,)
    ).fetchone()
    connection.close()

    if not existe:
        flash("Cadastro não encontrado.", "error")
    else:
        flash("Os cadastros antigos foram mantidos e desativados para preservar os QR Codes.", "info")
    return redirect(url_for("locations.locais"))
