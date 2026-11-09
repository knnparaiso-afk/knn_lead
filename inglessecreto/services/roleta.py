import hmac
import re
from urllib.parse import urlencode

from config import SECRET_KEY, UNIDADE
from database import get_connection
from telefones import normalizar_whatsapp


PREMIOS_ROLETA = (
    ("express", "Aula KNN Express", "Aula", "KNN Express"),
    ("kit", "Kit KNN", "Kit", "KNN"),
    ("desconto", "50% de desconto", "50%", "de desconto"),
)


def resultado_roleta(navegador_id):
    # O mesmo visitante recebe o mesmo prêmio em requisições simultâneas ou repetidas.
    sorteio = hmac.digest(SECRET_KEY.encode(), f"roleta:{navegador_id}".encode(), "sha256")
    fatia = int.from_bytes(sorteio, "big") % (2 * len(PREMIOS_ROLETA))
    tipo, premio, *_ = PREMIOS_ROLETA[fatia % len(PREMIOS_ROLETA)]
    return {"fatia": fatia, "tipo": tipo, "premio": premio}


def whatsapp_resgate_url():
    mensagem = "Oi! Girei a Roleta KNN e quero resgatar meu prêmio 🎁"
    return f"https://wa.me/{UNIDADE['whatsapp']}?" + urlencode({"text": mensagem})


def telefone_roleta(valor):
    numero = normalizar_whatsapp(valor)
    if len(numero) in (12, 13) and numero.startswith("55"):
        numero = numero[2:]
    if re.fullmatch(r"[1-9][0-9](?:9[0-9]{8}|[2-5][0-9]{7})", numero):
        return numero
    return ""


def registrar_resgate(navegador_id, whatsapp):
    resultado = resultado_roleta(navegador_id)
    connection = get_connection()
    try:
        # Repetir o envio é seguro. Outro giro não sobrescreve o prêmio do número.
        connection.execute(
            """
            INSERT INTO resgates_roleta (whatsapp, navegador_id, tipo, premio)
            VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING
            """,
            (whatsapp, navegador_id, resultado["tipo"], resultado["premio"]),
        )
        registro = connection.execute(
            "SELECT whatsapp FROM resgates_roleta WHERE navegador_id = ?",
            (navegador_id,),
        ).fetchone()
        connection.commit()
        return bool(registro and registro["whatsapp"] == whatsapp)
    finally:
        connection.close()


def resgate_do_navegador(navegador_id):
    connection = get_connection()
    try:
        registro = connection.execute(
            "SELECT tipo, premio FROM resgates_roleta WHERE navegador_id = ?",
            (navegador_id,),
        ).fetchone()
        return dict(registro) if registro else None
    finally:
        connection.close()
