from datetime import date
from urllib.parse import urlsplit

from flask import Blueprint, flash, redirect, render_template, request, url_for

from database import get_connection
from desafios import CATEGORIAS, DESAFIOS

from ..decorators import admin_required
from ..services.campaigns import (CADASTRO_DIRETO, cadastro_direto, gerar_codigo,
                                  normalizar_modalidade, situacao_campanha)
from ..services.qr_art import remover_arquivos_qr

bp = Blueprint("campaigns", __name__)
MODALIDADES = {CADASTRO_DIRETO: "Cadastro direto", **CATEGORIAS}


def _dados_formulario():
    f = request.form
    return {
        "nome": f.get("nome", "").strip(),
        "categoria": normalizar_modalidade(f.get("categoria", CADASTRO_DIRETO).strip()),
        "data_inicio": f.get("data_inicio", "").strip() or None,
        "data_fim": f.get("data_fim", "").strip() or None,
        "ativa": 1 if f.get("ativa") else 0,
        "exibir_faixa": 1 if f.get("exibir_faixa") or f.get("categoria") == "black_november" else 0,
        "chamada": f.get("chamada", "").strip(),
        "descricao": f.get("descricao", "").strip(),
        "comunidade_url": f.get("comunidade_url", "").strip(),
        "comunidade_nacional_url": f.get("comunidade_nacional_url", "").strip(),
    }


def _erro_periodo(dados):
    if dados["categoria"] not in MODALIDADES:
        return "Selecione uma modalidade válida."
    if len(dados["chamada"]) > 120 or len(dados["descricao"]) > 500:
        return "Revise os limites da chamada e da descrição."
    for campo in ("comunidade_url", "comunidade_nacional_url"):
        valor = dados[campo]
        try:
            url = urlsplit(valor)
            valido = url.scheme == "https" and url.hostname and not url.username and not url.password
        except ValueError:
            valido = False
        if valor and (len(valor) > 500 or not valido or any(c.isspace() for c in valor)):
            return "Informe links válidos das comunidades, começando com https://."
    for campo in ("data_inicio", "data_fim"):
        valor = dados[campo]
        if valor:
            try:
                if date.fromisoformat(valor).isoformat() != valor:
                    return "Informe datas válidas no formato ano-mês-dia."
            except ValueError:
                return "Informe datas válidas no formato ano-mês-dia."
    if (dados["data_inicio"] and dados["data_fim"]
            and dados["data_inicio"] > dados["data_fim"]):
        return "A data de término não pode ser anterior à data de início."
    return None


def _render_form(campanha, categoria, form_data=None):
    return render_template(
        "admin/campanha_form.html",
        campanha=campanha,
        form_data=form_data,
        categorias=MODALIDADES,
        desafios_preview=DESAFIOS.get(categoria, DESAFIOS["frases"]),
        todos_desafios=DESAFIOS,
    )


@bp.route("/admin/campanhas")
@admin_required
def campanhas():
    connection = get_connection()
    lista = connection.execute(
        """
        SELECT campanhas.*, COUNT(descobertas.id) AS total_descobertas,
               (SELECT COUNT(DISTINCT c.usuario_id) FROM cadastros_qr_avulso c JOIN qrs_avulsos q ON q.id = c.qr_avulso_id
                WHERE q.campanha_id = campanhas.id) AS total_cadastros
        FROM campanhas
        LEFT JOIN descobertas ON descobertas.campanha_id = campanhas.id
        GROUP BY campanhas.id
        ORDER BY campanhas.id DESC
        """
    ).fetchall()
    connection.close()
    situacoes = {campanha["id"]: situacao_campanha(campanha) for campanha in lista}
    return render_template("admin/campanhas.html", campanhas=lista, situacoes=situacoes)


@bp.route("/admin/campanhas/nova", methods=["GET", "POST"])
@admin_required
def nova_campanha():
    if request.method != "POST":
        categoria = normalizar_modalidade(request.args.get("categoria", CADASTRO_DIRETO))
        return _render_form(None, categoria, {"categoria": categoria, "ativa": 1, "exibir_faixa": 1})

    d = _dados_formulario()
    if not d["nome"] or len(d["nome"]) > 150:
        flash("Preencha um nome válido para a campanha.", "error")
        return _render_form(None, d["categoria"], d)
    erro_periodo = _erro_periodo(d)
    if erro_periodo:
        flash(erro_periodo, "error")
        return _render_form(None, d["categoria"], d)

    connection = get_connection()
    max_semana = connection.execute(
        "SELECT COALESCE(MAX(semana), 0) AS max_s FROM campanhas"
    ).fetchone()["max_s"]

    cursor = connection.execute(
        """
        INSERT INTO campanhas
        (codigo, nome, semana, frase, traducao, categoria, data_inicio, data_fim, ativa,
         chamada, descricao, comunidade_url, comunidade_nacional_url, exibir_faixa)
        VALUES (?, ?, ?, '', '', ?, ?, ?, ?, ?, ?, ?, ?, ?)
        RETURNING id
        """,
        (gerar_codigo(), d["nome"], max_semana + 1, d["categoria"],
         d["data_inicio"], d["data_fim"], d["ativa"], d["chamada"], d["descricao"],
         d["comunidade_url"], d["comunidade_nacional_url"], d["exibir_faixa"]),
    )
    campanha_id = cursor.fetchone()["id"]
    if d["exibir_faixa"]:
        connection.execute("UPDATE campanhas SET exibir_faixa = 0 WHERE id <> ?", (campanha_id,))
    if d["categoria"] == CADASTRO_DIRETO:
        for origem in ("qr", "landing"):
            connection.execute(
                "INSERT INTO qrs_avulsos (codigo, parceiro, campanha_id, origem) VALUES (?, ?, ?, ?)",
                (gerar_codigo(), d["nome"], campanha_id, origem),
            )
    connection.commit()
    connection.close()

    flash("Campanha criada! Seu primeiro QR de cadastro já está pronto." if d["categoria"] == CADASTRO_DIRETO
          else "Campanha criada! Agora gere o QR Code geral da campanha.", "success")
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
        if campanha["arquivada"]:
            connection.close()
            flash("Esta campanha está arquivada. Seu histórico foi preservado.", "error")
            return redirect(url_for("campaigns.campanhas"))
        d = _dados_formulario()
        if not d["nome"] or len(d["nome"]) > 150:
            connection.close()
            flash("Preencha um nome válido para a campanha.", "error")
            return _render_form(campanha, d["categoria"], d)
        erro_periodo = _erro_periodo(d)
        if (d["categoria"] == CADASTRO_DIRETO) != cadastro_direto(campanha):
            erro_periodo = "Crie outra campanha para mudar a modalidade e preservar os QR Codes existentes."
        if erro_periodo:
            connection.close()
            flash(erro_periodo, "error")
            return _render_form(campanha, d["categoria"], d)

        connection.execute(
            """
            UPDATE campanhas
            SET nome = ?, categoria = ?, data_inicio = ?, data_fim = ?, ativa = ?,
                chamada = ?, descricao = ?, comunidade_url = ?, comunidade_nacional_url = ?, exibir_faixa = ?
            WHERE id = ?
            """,
            (d["nome"], d["categoria"], d["data_inicio"], d["data_fim"], d["ativa"],
             d["chamada"], d["descricao"], d["comunidade_url"], d["comunidade_nacional_url"], d["exibir_faixa"], campanha_id),
        )
        if d["exibir_faixa"]:
            connection.execute("UPDATE campanhas SET exibir_faixa = 0 WHERE id <> ?", (campanha_id,))
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
        "SELECT * FROM campanhas WHERE id = ?", (campanha_id,)
    ).fetchone()

    if not campanha:
        connection.close()
        flash("Campanha não encontrada.", "error")
        return redirect(url_for("campaigns.campanhas"))

    if cadastro_direto(campanha):
        connection.execute("UPDATE campanhas SET ativa = 0, arquivada = 1, exibir_faixa = 0 WHERE id = ?", (campanha_id,))
        connection.commit()
        connection.close()
        flash("Campanha arquivada. Cadastros, origens, QR Codes e métricas foram preservados.", "success")
        return redirect(url_for("campaigns.campanhas"))

    connection.execute("UPDATE qrs_avulsos SET ativo = 0 WHERE campanha_id = ?", (campanha_id,))
    connection.execute("DELETE FROM campanhas WHERE id = ?", (campanha_id,))
    connection.commit()
    connection.close()

    remover_arquivos_qr(qr["codigo"] for qr in qrs)
    flash("Campanha e seus QR Codes foram excluídos.", "success")
    return redirect(url_for("campaigns.campanhas"))
