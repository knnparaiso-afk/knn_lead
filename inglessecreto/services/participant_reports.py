"""Uma leitura de participantes e origens para cadastro direto e desafios."""

ORIGENS_SQL = """
    SELECT d.usuario_id, c.id AS campanha_id, c.nome AS campanha_nome,
           c.categoria, q.codigo, 'qr' AS origem, d.data_hora AS data_entrada
    FROM descobertas d
    JOIN campanhas c ON c.id = d.campanha_id
    JOIN qr_codes q ON q.id = d.qr_code_id
    UNION ALL
    SELECT r.usuario_id, c.id, c.nome, c.categoria, q.codigo, q.origem, r.data_cadastro
    FROM cadastros_qr_avulso r
    JOIN qrs_avulsos q ON q.id = r.qr_avulso_id
    LEFT JOIN campanhas c ON c.id = q.campanha_id
"""


def listar_participantes(connection, campanha_id=None):
    pessoas = connection.execute(
        f"WITH origens AS ({ORIGENS_SQL}) SELECT u.* FROM usuarios u "
        "WHERE CAST(? AS INTEGER) IS NULL OR EXISTS ("
        "SELECT 1 FROM origens o WHERE o.usuario_id = u.id AND o.campanha_id = ?) "
        "ORDER BY u.data_cadastro DESC, u.id DESC", (campanha_id, campanha_id),
    ).fetchall()
    por_id = {row["id"]: {**dict(row), "origens": [], "total_descobertas": 0,
                           "total_cadastros": 0, "data_entrada": None} for row in pessoas}
    origens = connection.execute(
        f"WITH origens AS ({ORIGENS_SQL}) SELECT * FROM origens "
        "WHERE CAST(? AS INTEGER) IS NULL OR campanha_id = ? ORDER BY data_entrada, codigo",
        (campanha_id, campanha_id),
    ).fetchall()
    for row in origens:
        pessoa = por_id.get(row["usuario_id"])
        if pessoa is None:
            continue
        pessoa["origens"].append(dict(row))
        if pessoa["data_entrada"] is None:
            pessoa["data_entrada"] = row["data_entrada"]
        if row["categoria"] in ("frases", "jogos"):
            pessoa["total_descobertas"] += 1
        else:
            pessoa["total_cadastros"] += 1
    return list(por_id.values())
