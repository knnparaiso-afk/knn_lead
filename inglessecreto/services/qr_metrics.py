"""Eventos exclusivos do cadastro por QR avulso. O chamador controla a transação."""

EVENTOS_QR_AVULSO = {
    "acesso": "Acesso ao formulário",
    "cadastro_concluido": "Novo cadastro concluído",
    "cadastro_reenviado": "Cadastro reenviado",
    "erro_validacao": "Formulário com dados inválidos",
}


def registrar_evento_qr_avulso(connection, qr_id, evento):
    if evento not in EVENTOS_QR_AVULSO:
        raise ValueError("Evento de QR avulso inválido.")
    connection.execute(
        "INSERT INTO eventos_qr_avulso (qr_avulso_id, evento) VALUES (?, ?)",
        (qr_id, evento),
    )
