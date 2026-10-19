from flask import current_app, request, session
from itsdangerous import BadSignature, URLSafeTimedSerializer

from desafios import DESAFIOS, obter_desafio_por_id, sortear_desafio


HISTORY_COOKIE = "knn_desafios_vistos"
HISTORY_MAX_AGE = 86400 * 365


def _signer():
    return URLSafeTimedSerializer(current_app.secret_key, salt="knn-desafios-vistos-v1")


def sortear_para_navegador(codigo, categoria):
    """Mantém o desafio do QR e evita repetir frases entre novos QR Codes."""
    categoria = categoria if categoria in DESAFIOS else "frases"
    historico = {}
    token = request.cookies.get(HISTORY_COOKIE)
    if token:
        try:
            dados = _signer().loads(token, max_age=HISTORY_MAX_AGE)
            if isinstance(dados, dict):
                historico = dados
        except BadSignature:
            pass

    # Também considera frases que já estavam sorteadas antes desta atualização.
    if not historico:
        for chave, desafio_id in session.items():
            if chave.startswith("desafio_sorteado_"):
                for nome, desafios in DESAFIOS.items():
                    if any(d["id"] == desafio_id for d in desafios):
                        vistos = historico.setdefault(nome, [])
                        if desafio_id not in vistos:
                            vistos.append(desafio_id)

    ids_validos = {d["id"] for d in DESAFIOS[categoria]}
    vistos = historico.get(categoria, [])
    if not isinstance(vistos, list):
        vistos = []
    vistos = list(dict.fromkeys(d for d in vistos if isinstance(d, str) and d in ids_validos))

    chave = f"desafio_sorteado_{codigo}"
    desafio = obter_desafio_por_id(session.get(chave), categoria)
    if not desafio:
        desafio = sortear_desafio(categoria, excluir_ids=vistos)
        if len(vistos) == len(ids_validos):
            vistos = []
        session[chave] = desafio["id"]
        session.pop(f"desafio_acertado_{codigo}", None)

    if desafio["id"] in vistos:
        vistos.remove(desafio["id"])
    vistos.append(desafio["id"])
    historico[categoria] = vistos
    return desafio, historico


def guardar_historico(response, historico):
    response.set_cookie(
        HISTORY_COOKIE,
        _signer().dumps(historico),
        max_age=HISTORY_MAX_AGE,
        httponly=True,
        samesite="Lax",
        secure=current_app.config["SESSION_COOKIE_SECURE"] or request.is_secure,
    )
    return response
