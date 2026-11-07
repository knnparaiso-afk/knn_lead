import hmac
from urllib.parse import urlencode

from config import SECRET_KEY, UNIDADE


PREMIOS_ROLETA = (
    ("express", "Aula KNN Express", "Aula", "KNN Express"),
    ("kit", "Kit KNN", "Kit", "KNN"),
    ("desconto", "25% de desconto na matrícula", "25%", "de desconto"),
)


def resultado_roleta(navegador_id):
    # O mesmo visitante recebe o mesmo prêmio em requisições simultâneas ou repetidas.
    sorteio = hmac.digest(SECRET_KEY.encode(), f"roleta:{navegador_id}".encode(), "sha256")
    fatia = int.from_bytes(sorteio, "big") % (2 * len(PREMIOS_ROLETA))
    tipo, premio, *_ = PREMIOS_ROLETA[fatia % len(PREMIOS_ROLETA)]
    mensagem = f"Olá! Ganhei {premio} na roleta da KNN e quero resgatar meu prêmio."
    return {
        "fatia": fatia,
        "tipo": tipo,
        "premio": premio,
        "whatsapp_url": f"https://wa.me/{UNIDADE['whatsapp']}?" + urlencode({"text": mensagem}),
    }
