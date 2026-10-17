from flask import Blueprint, flash, redirect, render_template, request, url_for

from database import get_connection
from desafios import CATEGORIAS, DESAFIOS

from ..decorators import admin_required
from ..services.campaigns import gerar_codigo
from ..services.qr_art import remover_arquivos_qr

bp = Blueprint("campaigns", __name__)


def _dados_formulario():
    f = request.form
    return {
        "nome": f.get("nome", "").strip(),
        "categoria": f.get("categoria", "frases").strip(),
        "data_inicio": f.get("data_inicio", "").strip() or None,
        "data_fim": f.get("data_fim", "").strip() or None,
        "ativa": 1 if f.get("ativa") else 0,
    }


def _render_form(campanha, categoria):
    return render_template(
        "admin/campanha_form.html",
        campanha=campanha,
        categorias=CATEGORIAS,
        desafios_preview=DESAFIOS.get(categoria, DESAFIOS["frases"]),
        todos_desafios=DESAFIOS,
    )


@bp.route("/admin/campanhas")
@admin_required
def campanhas():
    connection = get_connection()
    lista = connection.execute(
        """
        SELECT campanhas.*, COUNT(descobertas.id) AS total_descobertas
        FROM campanhas
        LEFT JOIN descobertas ON descobertas.campanha_id = campanhas.id
        GROUP BY campanhas.id
        ORDER BY campanhas.id DESC
        """
    ).fetchall()
    connection.close()
    return render_template("admin/campanhas.html", campanhas=lista)


@bp.route("/admin/campanhas/nova", methods=["GET", "POST"])
@admin_required
def nova_campanha():
    if request.method != "POST":
        return _render_form(None, "frases")

    d = _dados_formulario()
    if not d["nome"] or len(d["nome"]) > 150:
        flash("Preencha um nome válido para a campanha.", "error")
        return _render_form(None, d["categoria"])

    connection = get_connection()
    max_semana = connection.execute(
        "SELECT COALESCE(MAX(semana), 0) AS max_s FROM campanhas"
    ).fetchone()["max_s"]

    cursor = connection.execute(
        """
        INSERT INTO campanhas
        (codigo, nome, semana, frase, traducao, categoria, data_inicio, data_fim, ativa)
        VALUES (?, ?, ?, '', '', ?, ?, ?, ?)
        RETURNING id
        """,
        (gerar_codigo(), d["nome"], max_semana + 1, d["categoria"],
         d["data_inicio"], d["data_fim"], d["ativa"]),
    )
    campanha_id = cursor.fetchone()["id"]
    connection.commit()
    connection.close()

    flash("Campanha criada! Agora selecione um local cadastrado para gerar o QR Code.", "success")
    return redirect(url_for("qr.gerenciar_qr", campanha_id=campanha_id))


@bp.route("/admin/campanhas/<int:campanha_id>/editar", methods=["GET", "POST"])
@admin_required
def editar_campanha(campanha_id):
    connection = get_connection()
    campanha = connection.execute(
        "SELECT * FROM campanhas WHERE id = ?", (campanha_id,)
    ).fetchone()

    if not campanha:
        connection.close()
        flash("Campanha não encontrada.", "error")
        return redirect(url_for("campaigns.campanhas"))

    if request.method == "POST":
        d = _dados_formulario()
        if not d["nome"] or len(d["nome"]) > 150:
            connection.close()
            flash("Preencha um nome válido para a campanha.", "error")
            return _render_form(campanha, d["categoria"])

        connection.execute(
            """
            UPDATE campanhas
            SET nome = ?, categoria = ?, data_inicio = ?, data_fim = ?, ativa = ?
            WHERE id = ?
            """,
            (d["nome"], d["categoria"], d["data_inicio"], d["data_fim"], d["ativa"], campanha_id),
        )
        connection.commit()
        connection.close()
        flash("Campanha atualizada com sucesso.", "success")
        return redirect(url_for("campaigns.campanhas"))

    connection.close()
    categoria_atual = campanha["categoria"] if "categoria" in campanha.keys() and campanha["categoria"] else "frases"
    return _render_form(campanha, categoria_atual)


@bp.route("/admin/campanhas/<int:campanha_id>/excluir", methods=["POST"])
@admin_required
def excluir_campanha(campanha_id):
    connection = get_connection()
    qrs = connection.execute(
        "SELECT codigo FROM qr_codes WHERE campanha_id = ?", (campanha_id,)
    ).fetchall()
    campanha = connection.execute(
        "SELECT id FROM campanhas WHERE id = ?", (campanha_id,)
    ).fetchone()

    if not campanha:
        connection.close()
        flash("Campanha não encontrada.", "error")
        return redirect(url_for("campaigns.campanhas"))

    connection.execute("DELETE FROM campanhas WHERE id = ?", (campanha_id,))
    connection.commit()
    connection.close()

    remover_arquivos_qr(qr["codigo"] for qr in qrs)
    flash("Campanha e seus QR Codes foram excluídos.", "success")
    return redirect(url_for("campaigns.campanhas"))
