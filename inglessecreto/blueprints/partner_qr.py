import io

import qrcode
from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for

from config import BASE_URL
from database import get_connection
from ..decorators import admin_required
from ..security import permitir_requisicao
from ..services.campaigns import cadastro_direto, gerar_codigo
from ..services.black_qr_art import gerar_arte_black
from ..services.qr_metrics import EVENTOS_QR_AVULSO

bp = Blueprint("partner_qr", __name__)


@bp.route("/admin/qr-avulso", methods=["GET", "POST"])
@admin_required
def lista_qrs():
    campanha_id = request.values.get("campanha_id", type=int)
    connection = get_connection()
    try:
        campanha = connection.execute("SELECT * FROM campanhas WHERE id = ?", (campanha_id,)).fetchone() if campanha_id else None
        if campanha_id and not cadastro_direto(campanha):
            abort(404)
        disponiveis = connection.execute(
            "SELECT id, codigo, parceiro FROM qrs_avulsos WHERE campanha_id IS NULL AND ativo = 1 AND origem = 'qr' ORDER BY id DESC"
        ).fetchall() if campanha else []
    finally:
        connection.close()

    def voltar():
        return redirect(url_for("partner_qr.lista_qrs", campanha_id=campanha_id))

    if request.method == "POST":
        if campanha and campanha["arquivada"]:
            abort(409)
        if not permitir_requisicao("criar_qr_avulso", 30, 600):
            flash("Muitas solicitações. Aguarde e tente novamente.", "error")
            return voltar()
        parceiro = campanha["nome"] if campanha else " ".join(request.form.get("parceiro", "").split()) or "Cadastro direto"
        if len(parceiro) > 150:
            flash("A identificação deve ter até 150 caracteres.", "error")
            return voltar()
        codigo = gerar_codigo()
        connection = get_connection()
        try:
            connection.execute(
                "INSERT INTO qrs_avulsos (codigo, parceiro, campanha_id) VALUES (?, ?, ?)",
                (codigo, parceiro, campanha_id),
            )
            connection.commit()
        finally:
            connection.close()
        flash("QR avulso criado. O link abre direto no cadastro.", "success")
        return voltar()

    connection = get_connection()
    qrs = connection.execute(
        """SELECT q.id, q.codigo, q.parceiro, q.data_criacao, q.ativo, q.campanha_id, q.origem,
                  campanhas.nome AS campanha_nome, campanhas.codigo AS campanha_codigo,
                  COUNT(c.id) AS total_cadastros,
                  (SELECT COUNT(*) FROM eventos_qr_avulso e
                   WHERE e.qr_avulso_id = q.id AND e.evento = 'acesso') AS total_acessos
           FROM qrs_avulsos q
           LEFT JOIN campanhas ON campanhas.id = q.campanha_id
           LEFT JOIN cadastros_qr_avulso c ON c.qr_avulso_id = q.id
           WHERE (CAST(? AS INTEGER) IS NULL OR q.campanha_id = ?)
           GROUP BY q.id, campanhas.nome, campanhas.codigo ORDER BY q.id DESC""", (campanha_id, campanha_id),
    ).fetchall()
    connection.close()
    return render_template("admin/qr_avulso.html", qrs=qrs, base_url=BASE_URL,
                           campanha=campanha, disponiveis=disponiveis)


@bp.route("/admin/qr-avulso/vincular", methods=["POST"])
@admin_required
def vincular():
    campanha_id = request.form.get("campanha_id", type=int)
    qr_id = request.form.get("qr_id", type=int)
    connection = get_connection()
    try:
        campanha = connection.execute(
            "SELECT * FROM campanhas WHERE id = ?", (campanha_id,),
        ).fetchone()
        if not cadastro_direto(campanha) or campanha["arquivada"]:
            abort(404)
        atualizado = connection.execute(
            "UPDATE qrs_avulsos SET campanha_id = ? WHERE id = ? AND campanha_id IS NULL AND ativo = 1 AND origem = 'qr' RETURNING id",
            (campanha_id, qr_id),
        ).fetchone()
        if not atualizado:
            abort(404)
        connection.commit()
    finally:
        connection.close()
    flash("Os códigos, cadastros e métricas do QR foram preservados.", "success")
    return redirect(url_for("partner_qr.lista_qrs", campanha_id=campanha_id))


@bp.route("/admin/qr-avulso/<int:qr_id>/imagem")
@admin_required
def imagem_qr(qr_id):
    connection = get_connection()
    qr = connection.execute("SELECT codigo FROM qrs_avulsos WHERE id = ?", (qr_id,)).fetchone()
    connection.close()
    if not qr:
        abort(404)
    if request.args.get("arte") == "black":
        return send_file(gerar_arte_black(qr["codigo"]), mimetype="image/png",
                         as_attachment=request.args.get("preview") != "1",
                         download_name=f"black-november-{qr['codigo']}.png")
    image = qrcode.make(f"{BASE_URL}/cadastro-parceiro/{qr['codigo']}")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return send_file(buffer, mimetype="image/png",
                     as_attachment=request.args.get("preview") != "1",
                     download_name=f"qr-avulso-{qr['codigo']}.png")


@bp.route("/admin/qr-avulso/<int:qr_id>/metricas")
@admin_required
def metricas(qr_id):
    connection = get_connection()
    try:
        qr = connection.execute("SELECT * FROM qrs_avulsos WHERE id = ?", (qr_id,)).fetchone()
        if not qr:
            abort(404)
        totais = {evento: 0 for evento in EVENTOS_QR_AVULSO}
        for row in connection.execute(
            "SELECT evento, COUNT(*) AS total FROM eventos_qr_avulso "
            "WHERE qr_avulso_id = ? GROUP BY evento", (qr_id,),
        ).fetchall():
            totais[row["evento"]] = row["total"]
        eventos = connection.execute(
            "SELECT evento, data_evento FROM eventos_qr_avulso "
            "WHERE qr_avulso_id = ? ORDER BY id DESC LIMIT 100", (qr_id,),
        ).fetchall()
        primeiro_evento = connection.execute(
            "SELECT MIN(data_evento) AS data FROM eventos_qr_avulso WHERE qr_avulso_id = ?",
            (qr_id,),
        ).fetchone()["data"]
        total_cadastros = connection.execute(
            "SELECT COUNT(*) AS total FROM cadastros_qr_avulso WHERE qr_avulso_id = ?",
            (qr_id,),
        ).fetchone()["total"]
    finally:
        connection.close()
    conversao = (100 * totais["cadastro_concluido"] / totais["acesso"]
                 if totais["acesso"] else None)
    return render_template(
        "admin/metricas_qr_avulso.html", qr=qr, totais=totais, eventos=eventos,
        nomes_eventos=EVENTOS_QR_AVULSO, primeiro_evento=primeiro_evento,
        total_cadastros=total_cadastros, conversao=conversao,
    )


@bp.route("/admin/cadastros-parceiros")
@admin_required
def cadastros():
    campanha_id = request.args.get("campanha_id", type=int)
    connection = get_connection()
    registros = connection.execute(
        """SELECT c.data_cadastro, u.nome, u.whatsapp, u.email, u.idade,
                  q.parceiro, q.codigo, q.origem, campanhas.nome AS campanha_nome
           FROM cadastros_qr_avulso c
           JOIN usuarios u ON u.id = c.usuario_id
           JOIN qrs_avulsos q ON q.id = c.qr_avulso_id
           LEFT JOIN campanhas ON campanhas.id = q.campanha_id
           WHERE (CAST(? AS INTEGER) IS NULL OR q.campanha_id = ?)
           ORDER BY c.data_cadastro DESC, c.id DESC""", (campanha_id, campanha_id),
    ).fetchall()
    connection.close()
    return render_template("admin/cadastros_parceiros.html", registros=registros, campanha_id=campanha_id)


@bp.route("/admin/campanhas/<int:campanha_id>/metricas-cadastro")
@admin_required
def metricas_campanha(campanha_id):
    connection = get_connection()
    try:
        campanha = connection.execute("SELECT * FROM campanhas WHERE id = ?", (campanha_id,)).fetchone()
        if not cadastro_direto(campanha):
            abort(404)
        totais = {evento: 0 for evento in EVENTOS_QR_AVULSO}
        for row in connection.execute(
            "SELECT e.evento, COUNT(*) AS total FROM eventos_qr_avulso e "
            "JOIN qrs_avulsos q ON q.id = e.qr_avulso_id WHERE q.campanha_id = ? GROUP BY e.evento", (campanha_id,),
        ).fetchall():
            totais[row["evento"]] = row["total"]
        participantes = connection.execute(
            "SELECT COUNT(DISTINCT c.usuario_id) AS total FROM cadastros_qr_avulso c "
            "JOIN qrs_avulsos q ON q.id = c.qr_avulso_id WHERE q.campanha_id = ?", (campanha_id,),
        ).fetchone()["total"]
        origens = connection.execute(
            "SELECT q.id, q.codigo, q.origem, q.parceiro, "
            "(SELECT COUNT(*) FROM cadastros_qr_avulso c WHERE c.qr_avulso_id = q.id) AS cadastros, "
            "(SELECT COUNT(*) FROM eventos_qr_avulso e WHERE e.qr_avulso_id = q.id AND e.evento = 'acesso') AS acessos "
            "FROM qrs_avulsos q WHERE q.campanha_id = ? ORDER BY q.id", (campanha_id,),
        ).fetchall()
        eventos = connection.execute(
            "SELECT e.evento, e.data_evento, q.codigo, q.origem FROM eventos_qr_avulso e "
            "JOIN qrs_avulsos q ON q.id = e.qr_avulso_id WHERE q.campanha_id = ? ORDER BY e.id DESC LIMIT 100", (campanha_id,),
        ).fetchall()
    finally:
        connection.close()
    return render_template("admin/metricas_cadastro.html", campanha=campanha, totais=totais,
                           participantes=participantes, origens=origens, eventos=eventos,
                           nomes_eventos=EVENTOS_QR_AVULSO)
