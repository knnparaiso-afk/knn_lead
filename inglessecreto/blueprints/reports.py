"""Dashboard, participantes, descobertas e English Pass (admin)."""
from flask import Blueprint, flash, redirect, render_template, url_for

from config import ENGLISH_PASS_REQUIRED
from database import get_connection

from ..decorators import admin_required
from ..services.campaigns import filtro_campanha_vigente, parametros_vigencia

bp = Blueprint("reports", __name__)


def _contar(connection, sql, parameters=()):
    return connection.execute(sql, parameters).fetchone()["total"]


@bp.route("/admin")
@bp.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    connection = get_connection()
    participantes = _contar(connection, "SELECT COUNT(*) AS total FROM usuarios")
    descobertas = _contar(connection, "SELECT COUNT(*) AS total FROM descobertas")
    passes = _contar(connection, "SELECT COUNT(*) AS total FROM premios")
    locais_ativos = _contar(connection, "SELECT COUNT(*) AS total FROM locais WHERE ativo = 1")
    campanhas_ativas = connection.execute(
        f"""
        SELECT
            campanhas.*,
            COUNT(DISTINCT descobertas.id) AS total_descobertas,
            COUNT(DISTINCT qr_codes.id) AS total_qrs
        FROM campanhas
        LEFT JOIN descobertas ON descobertas.campanha_id = campanhas.id
        LEFT JOIN qr_codes ON qr_codes.campanha_id = campanhas.id
        WHERE {filtro_campanha_vigente()}
        GROUP BY campanhas.id
        ORDER BY campanhas.id DESC
        """,
        parametros_vigencia(),
    ).fetchall()
    total_campanhas_ativas = len(campanhas_ativas)
    connection.close()

    return render_template(
        "admin/dashboard.html",
        campanhas_ativas=total_campanhas_ativas,
        participantes=participantes,
        descobertas=descobertas,
        passes=passes,
        locais_ativos=locais_ativos,
        campanhas_ativas_lista=campanhas_ativas,
    )


@bp.route("/admin/participantes")
@admin_required
def participantes():
    connection = get_connection()
    lista = connection.execute(
        """
        SELECT usuarios.*, COUNT(descobertas.id) AS total_descobertas
        FROM usuarios
        LEFT JOIN descobertas ON descobertas.usuario_id = usuarios.id
        GROUP BY usuarios.id
        ORDER BY total_descobertas DESC
        """
    ).fetchall()
    connection.close()
    return render_template("admin/participantes.html",
                           participantes=lista, pass_required=ENGLISH_PASS_REQUIRED)


@bp.route("/admin/participantes/<int:usuario_id>/excluir", methods=["POST"])
@admin_required
def excluir_participante(usuario_id):
    connection = get_connection()
    try:
        # Exclusão em cascata explícita para compatibilidade SQLite e PostgreSQL
        connection.execute("DELETE FROM registros_consentimento WHERE usuario_id = ?", (usuario_id,))
        connection.execute("DELETE FROM premios WHERE usuario_id = ?", (usuario_id,))
        connection.execute("DELETE FROM descobertas WHERE usuario_id = ?", (usuario_id,))
        connection.execute("DELETE FROM usuarios WHERE id = ?", (usuario_id,))
        connection.commit()
        flash("Participante e seus registros foram excluídos com sucesso.", "success")
    except Exception:
        connection.rollback()
        flash("Erro ao excluir participante.", "error")
    finally:
        connection.close()
    return redirect(url_for("reports.participantes"))


@bp.route("/admin/descobertas")
@admin_required
def descobertas():
    connection = get_connection()
    lista = connection.execute(
        """
        SELECT
            descobertas.*,
            usuarios.nome AS usuario_nome,
            usuarios.whatsapp,
            campanhas.nome AS campanha_nome,
            campanhas.frase,
            campanhas.semana,
            locais.nome AS local_nome,
            locais.parceiro,
            qr_codes.codigo AS qr_codigo,
            COUNT(*) OVER (
                PARTITION BY descobertas.usuario_id
            ) AS total_qrs_pessoa,
            ROW_NUMBER() OVER (
                PARTITION BY descobertas.usuario_id
                ORDER BY descobertas.data_hora ASC, descobertas.id ASC
            ) AS ordem_qr
        FROM descobertas
        INNER JOIN usuarios ON usuarios.id = descobertas.usuario_id
        INNER JOIN campanhas ON campanhas.id = descobertas.campanha_id
        INNER JOIN locais ON locais.id = descobertas.local_id
        INNER JOIN qr_codes ON qr_codes.id = descobertas.qr_code_id
        ORDER BY descobertas.data_hora DESC, descobertas.id DESC
        """
    ).fetchall()
    connection.close()

    pessoas = {}
    for registro in lista:
        descoberta = dict(registro)
        usuario_id = descoberta["usuario_id"]
        if usuario_id not in pessoas:
            pessoas[usuario_id] = {
                "id": usuario_id,
                "nome": descoberta["usuario_nome"],
                "whatsapp": descoberta["whatsapp"],
                "total_qrs": descoberta["total_qrs_pessoa"],
                "descobertas": [],
            }
        pessoas[usuario_id]["descobertas"].append(descoberta)

    for pessoa in pessoas.values():
        pessoa["descobertas"].sort(key=lambda item: (item["ordem_qr"], item["id"]))

    return render_template(
        "admin/descobertas.html",
        pessoas=list(pessoas.values()),
    )


@bp.route("/admin/pass")
@admin_required
def admin_pass():
    connection = get_connection()
    premios = connection.execute(
        """
        SELECT
            premios.*,
            usuarios.nome AS usuario_nome,
            usuarios.whatsapp,
            recompensas.nome AS recompensa_nome
        FROM premios
        INNER JOIN usuarios ON usuarios.id = premios.usuario_id
        INNER JOIN recompensas ON recompensas.id = premios.recompensa_id
        ORDER BY premios.data_desbloqueio DESC
        """
    ).fetchall()
    recompensas = connection.execute("SELECT * FROM recompensas ORDER BY id").fetchall()
    connection.close()
    return render_template("admin/pass.html", premios=premios, recompensas=recompensas)


@bp.route("/admin/pass/<int:premio_id>/utilizar", methods=["POST"])
@admin_required
def utilizar_premio(premio_id):
    connection = get_connection()
    connection.execute(
        """
        UPDATE premios
        SET status = 'utilizado', data_utilizacao = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (premio_id,),
    )
    connection.commit()
    connection.close()
    flash("Recompensa marcada como utilizada.", "success")
    return redirect(url_for("reports.admin_pass"))
