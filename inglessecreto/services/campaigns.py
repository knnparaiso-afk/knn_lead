import secrets
import string
from datetime import date, datetime, time, timedelta

from database import get_connection
from ..utils import TZ_BRASIL, hoje_brasilia

BLACK_NOVEMBER = "black_november"
CADASTRO_DIRETO = "cadastro_direto"


def normalizar_modalidade(categoria):
    """Aceita formulários/links antigos sem acoplar a mecânica ao nome Black."""
    return CADASTRO_DIRETO if categoria == BLACK_NOVEMBER else categoria


def cadastro_direto(campanha):
    return bool(campanha) and normalizar_modalidade(campanha["categoria"]) == CADASTRO_DIRETO


def periodo_campanha(campanha, agora=None):
    """Prazo real, até o fim do último dia no horário de Brasília."""
    if not campanha or not campanha["data_fim"]:
        return None
    try:
        fim = datetime.combine(date.fromisoformat(campanha["data_fim"]) + timedelta(days=1), time.min, TZ_BRASIL)
        inicio = (datetime.combine(date.fromisoformat(campanha["data_inicio"]), time.min, TZ_BRASIL)
                  if campanha["data_inicio"] else None)
    except (ValueError, OverflowError):
        return None
    percentual = None
    if inicio and inicio < fim:
        atual = agora or datetime.now(TZ_BRASIL)
        percentual = int(max(0, min(100, (atual - inicio).total_seconds() / (fim - inicio).total_seconds() * 100)))
    return {"inicio": inicio.isoformat() if inicio else "", "fim": fim.isoformat(), "percentual": percentual}


def filtro_campanha_vigente(alias="campanhas"):
    """Filtro SQL portátil para as datas ISO (YYYY-MM-DD) das campanhas."""
    return (
        f"{alias}.ativa = 1 AND {alias}.arquivada = 0 "
        f"AND ({alias}.data_inicio IS NULL OR {alias}.data_inicio = '' OR {alias}.data_inicio <= ?) "
        f"AND ({alias}.data_fim IS NULL OR {alias}.data_fim = '' OR {alias}.data_fim >= ?)"
    )


def parametros_vigencia():
    hoje = hoje_brasilia().isoformat()
    return (hoje, hoje)


def situacao_campanha(campanha):
    """Estado exibido no admin e usado pelo QR, sem alterar o banco."""
    hoje = hoje_brasilia().isoformat()
    if "arquivada" in campanha.keys() and campanha["arquivada"]:
        return "arquivada"
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
