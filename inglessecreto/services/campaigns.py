import secrets
import string

from database import get_connection
from ..utils import hoje_brasilia

BLACK_NOVEMBER = "black_november"


def filtro_campanha_vigente(alias="campanhas"):
    """Filtro SQL portátil para as datas ISO (YYYY-MM-DD) das campanhas."""
    return (
        f"{alias}.ativa = 1 "
        f"AND ({alias}.data_inicio IS NULL OR {alias}.data_inicio = '' OR {alias}.data_inicio <= ?) "
        f"AND ({alias}.data_fim IS NULL OR {alias}.data_fim = '' OR {alias}.data_fim >= ?)"
    )


def parametros_vigencia():
    hoje = hoje_brasilia().isoformat()
    return (hoje, hoje)


def situacao_campanha(campanha):
    """Estado exibido no admin e usado pelo QR, sem alterar o banco."""
    hoje = hoje_brasilia().isoformat()
    if not campanha["ativa"]:
        return "inativa"
    if campanha["data_inicio"] and campanha["data_inicio"] > hoje:
        return "agendada"
    if campanha["data_fim"] and campanha["data_fim"] < hoje:
        return "encerrada"
    return "ativa"


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
            existe_avulso = connection.execute(
                "SELECT id FROM qrs_avulsos WHERE codigo = ?", (codigo,)
            ).fetchone()
        finally:
            connection.close()
        if not existe_campanha and not existe_qr and not existe_avulso:
            return codigo
