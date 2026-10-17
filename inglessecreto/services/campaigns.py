import secrets
import string

from database import get_connection
from ..utils import hoje_brasilia


def desativar_campanhas_expiradas():
    """before_request: desativa campanhas cuja data_fim já passou."""
    hoje = hoje_brasilia().strftime("%Y-%m-%d")
    connection = get_connection()
    try:
        connection.execute(
            """
            UPDATE campanhas
            SET ativa = 0
            WHERE ativa = 1
              AND data_fim IS NOT NULL
              AND TRIM(data_fim) != ''
              AND data_fim < ?
            """,
            (hoje,),
        )
        connection.commit()
    finally:
        connection.close()


def gerar_codigo(tamanho=12):
    caracteres = string.ascii_uppercase + string.digits
    while True:
        codigo = "".join(secrets.choice(caracteres) for _ in range(tamanho))
        connection = get_connection()
        try:
            existe_campanha = connection.execute(
                "SELECT id FROM campanhas WHERE codigo = ?", (codigo,)
            ).fetchone()
            existe_qr = connection.execute(
                "SELECT id FROM qr_codes WHERE codigo = ?", (codigo,)
            ).fetchone()
        finally:
            connection.close()
        if not existe_campanha and not existe_qr:
            return codigo
