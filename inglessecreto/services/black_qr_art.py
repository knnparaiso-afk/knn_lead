"""Cartaz Black November com a imagem fornecida e QR legível em módulos inteiros."""
import io
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageFont

from config import BASE_URL

ARTE_BLACK = Path(__file__).resolve().parents[2] / "static/img/black-november-knn.jpeg"
FONTE_BLACK = Path(__file__).resolve().parents[2] / "static/fonts/Vera.ttf"


def gerar_arte_black(codigo):
    poster = Image.new("RGB", (1254, 2150), "#030613")
    with Image.open(ARTE_BLACK) as artwork:
        poster.paste(artwork.convert("RGB"), (0, 0))
    draw = ImageDraw.Draw(poster)
    draw.text((627, 1300), "SEU NOVO IDIOMA COMEÇA AQUI", font=ImageFont.truetype(str(FONTE_BLACK), size=38), fill="white", anchor="mt")
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=1, border=4)
    qr.add_data(f"{BASE_URL}/cadastro-parceiro/{codigo}")
    qr.make(fit=True)
    qr.box_size = max(1, 560 // (qr.modules_count + 8))
    bitmap = qr.make_image(fill_color="#030613", back_color="white").convert("RGB")
    poster.paste(bitmap, ((1254 - bitmap.width) // 2, 1400))
    draw.text((627, 2010), "Material gratuito + isenção da taxa de matrícula", font=ImageFont.truetype(str(FONTE_BLACK), size=35), fill="#ff6b2b", anchor="mt")
    draw.text((627, 2075), "Aponte a câmera e faça seu cadastro.", font=ImageFont.truetype(str(FONTE_BLACK), size=30), fill="white", anchor="mt")
    output = io.BytesIO()
    poster.save(output, format="PNG", dpi=(200, 200))
    output.seek(0)
    return output
