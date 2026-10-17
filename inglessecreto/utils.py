import re
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

TZ_BRASIL = ZoneInfo("America/Sao_Paulo")


def hoje_brasilia():
    """Data atual no horário de Brasília (o servidor roda em UTC)."""
    return datetime.now(TZ_BRASIL).date()


def normalizar_resposta(valor):
    """Compara respostas sem diferenciar maiúsculas, acentos ou pontuação."""
    texto = unicodedata.normalize("NFD", valor.lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()
