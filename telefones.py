import re


def normalizar_whatsapp(valor):
    """Chave do telefone nacional com DDD, sem máscara ou espaços."""
    return re.sub(r"[^0-9]", "", valor or "")
