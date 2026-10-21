"""Geração da arte do QR Code (Pillow + qrcode) e gestão dos arquivos PNG."""
import os

import qrcode
from PIL import Image

from config import BASE_URL

QR_DIR = os.path.join("instance", "qrcodes")
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
QR_ARTES = {
    "pista-001": {
        "nome": "Arte 1",
        "preview": "images/qr-templates/pista-001.png",
        "preview_a5": "images/qr-templates/pista-001-a5.png",
        "thumbnail": "images/qr-templates/pista-001-thumb.jpg",
    },
    "pista-003": {
        "nome": "Arte 2",
        "preview": "images/qr-templates/pista-003.png",
        "thumbnail": "images/qr-templates/pista-003-thumb.jpg",
    },
}
ARTE_QR_PADRAO = "pista-001"
# As duas artes foram normalizadas para A4 a 300 dpi; o campo central tem o mesmo centro.
A4_SIZE = (2480, 3508)
A5_SIZE = (1748, 2480)
QR_CENTER = (1240, 2069)
# Mantém o código com folga dentro do contorno pontilhado de ambas as artes.
QR_MAX_SIZE = 660
TAMANHOS_PAPEL = {
    "a4": {"nome": "A4", "pixels": A4_SIZE, "largura_mm": 210, "altura_mm": 297},
    "a5": {"nome": "A5", "pixels": A5_SIZE, "largura_mm": 148, "altura_mm": 210},
}


def normalizar_arte_qr(arte):
    return arte if arte in QR_ARTES else ARTE_QR_PADRAO


def normalizar_tamanho_papel(tamanho):
    return tamanho if tamanho in TAMANHOS_PAPEL else "a4"


def artes_qr_disponiveis():
    return [
        {"id": chave, **dados}
        for chave, dados in QR_ARTES.items()
    ]


def caminho_qr(codigo, arte=ARTE_QR_PADRAO, tamanho="a4"):
    arte = normalizar_arte_qr(arte)
    tamanho = normalizar_tamanho_papel(tamanho)
    sufixo = f"-{tamanho}" if tamanho != "a4" else ""
    return os.path.join(QR_DIR, f"{codigo}-{arte}{sufixo}.png")


def remover_arquivos_qr(codigos):
    for codigo in codigos:
        caminhos = [
            caminho_qr(codigo, arte, tamanho)
            for arte in QR_ARTES
            for tamanho in TAMANHOS_PAPEL
        ]
        caminhos.append(os.path.join(QR_DIR, f"{codigo}.png"))
        for caminho in caminhos:
            if os.path.exists(caminho):
                os.remove(caminho)


def gerar_arte_qrcode(codigo, arte=ARTE_QR_PADRAO, tamanho="a4"):
    """Aplica o QR no espaço central da arte e salva o PNG no tamanho escolhido."""
    arte = normalizar_arte_qr(arte)
    tamanho = normalizar_tamanho_papel(tamanho)
    especificacao = TAMANHOS_PAPEL[tamanho]
    largura, altura = especificacao["pixels"]
    caminho = caminho_qr(codigo, arte, tamanho)
    if os.path.isfile(caminho):
        return caminho

    dados_arte = QR_ARTES[arte]
    chave_preview = "preview_a5" if tamanho == "a5" else "preview"
    caminho_fundo = os.path.join(
        ROOT_DIR, "static", dados_arte.get(chave_preview, dados_arte["preview"])
    )

    with Image.open(caminho_fundo) as fundo:
        img = fundo.convert("RGB")
    if img.size != (largura, altura):
        img = img.resize((largura, altura), Image.Resampling.LANCZOS)

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=1,
        border=4,
    )
    qr.add_data(f"{BASE_URL}/e/{codigo}")
    qr.make(fit=True)
    qr_limite = round(QR_MAX_SIZE * largura / A4_SIZE[0])
    qr.box_size = max(1, qr_limite // (qr.modules_count + qr.border * 2))
    qr_img = qr.make_image(fill_color="#111827", back_color="white").convert("RGB")

    centro_x = largura // 2
    centro_y = round(altura * QR_CENTER[1] / A4_SIZE[1])
    qr_x = centro_x - qr_img.width // 2
    qr_y = centro_y - qr_img.height // 2
    img.paste(qr_img, (qr_x, qr_y))

    os.makedirs(QR_DIR, exist_ok=True)
    # Evita o modo optimize, que recomprime cada cartaz e torna a troca de arte lenta.
    img.save(caminho, format="PNG", compress_level=3, dpi=(300, 300))
    return caminho
