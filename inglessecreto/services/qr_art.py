"""Geração da arte do QR Code (Pillow + qrcode) e gestão dos arquivos PNG."""
import os

import qrcode
from PIL import Image, ImageDraw, ImageFont

from config import BASE_URL

QR_DIR = os.path.join("instance", "qrcodes")


def caminho_qr(codigo):
    return os.path.join(QR_DIR, f"{codigo}.png")


def remover_arquivos_qr(codigos):
    for codigo in codigos:
        caminho = caminho_qr(codigo)
        if os.path.exists(caminho):
            os.remove(caminho)


def carregar_fonte(nomes, tamanho):
    """Carrega fontes legíveis no Windows local e no Linux do Render."""
    pastas = []
    windir = os.environ.get("WINDIR")
    if windir:
        pastas.append(os.path.join(windir, "Fonts"))
    elif os.name == "nt":
        pastas.append(os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Fonts"))

    pastas.extend([
        "/usr/share/fonts/truetype/dejavu",
        "/usr/share/fonts/truetype/liberation2",
        "/usr/share/fonts/truetype/liberation",
        "/usr/share/fonts/truetype/msttcorefonts",
        "/usr/local/share/fonts",
    ])

    def tentar(candidatas):
        for pasta in pastas:
            for nome in candidatas:
                caminho = os.path.join(pasta, nome)
                if os.path.isfile(caminho):
                    try:
                        return ImageFont.truetype(caminho, tamanho)
                    except (OSError, ValueError):
                        continue
        return None

    fonte = tentar(nomes)
    if fonte:
        return fonte

    nomes_lower = " ".join(nomes).lower()
    negrito = any(m in nomes_lower for m in ("bd", "bold", "segoeuib"))
    alternativas = (
        ["DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "Lato-Bold.ttf"]
        if negrito else
        ["DejaVuSans.ttf", "LiberationSans-Regular.ttf", "Lato-Regular.ttf"]
    )
    fonte = tentar(alternativas)
    if fonte:
        return fonte

    try:
        return ImageFont.load_default(size=tamanho)  # Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()


def quebrar_texto(texto, fonte, max_largura, draw):
    palavras = (texto or "").split()
    linhas, linha_atual = [], []
    for palavra in palavras:
        teste = " ".join(linha_atual + [palavra])
        try:
            bbox = draw.textbbox((0, 0), teste, font=fonte)
            largura = bbox[2] - bbox[0]
        except Exception:
            largura = len(teste) * 12
        if largura <= max_largura:
            linha_atual.append(palavra)
        else:
            if linha_atual:
                linhas.append(" ".join(linha_atual))
                linha_atual = [palavra]
            else:
                linhas.append(palavra)
                linha_atual = []
    if linha_atual:
        linhas.append(" ".join(linha_atual))
    return linhas or [texto or ""]


def gerar_arte_qrcode(codigo, campanha, local):
    """Gera a arte pronta para impressão e retorna o caminho do PNG."""
    W, H = 1080, 1560
    img = Image.new("RGB", (W, H), color="#FBFBFB")
    draw = ImageDraw.Draw(img)

    VERMELHO, PRETO, CINZA = "#ED1B2F", "#111827", "#4B5563"
    CINZA_CLARO, BRANCO = "#E5E7EB", "#FFFFFF"
    BOLD = ["arialbd.ttf", "segoeuib.ttf"]
    REGULAR = ["arial.ttf", "segoeui.ttf"]

    # 1. Header
    draw.rectangle([(0, 0), (W, 140)], fill=VERMELHO)
    draw.text((W / 2, 50), "KNN IDIOMAS", fill=BRANCO, font=carregar_fonte(BOLD, 46), anchor="mm")
    draw.text(
        (W / 2, 100), "INGLÊS SECRETO · DESAFIO HALLOWEEN",
        fill="#FFE4E6", font=carregar_fonte(REGULAR, 22), anchor="mm",
    )

    # 2. Informações de Referência (Campanha & Local)
    try:
        nome_campanha = (campanha["nome"] if campanha and "nome" in campanha.keys() else "MISSÃO HALLOWEEN").strip().upper()
    except Exception:
        nome_campanha = (dict(campanha).get("nome") if campanha else "MISSÃO HALLOWEEN").strip().upper()

    try:
        local_nome = (local["nome"] if local and "nome" in local.keys() else "PONTO DA MISSÃO").strip().upper()
    except Exception:
        local_nome = (dict(local).get("nome") if local else "PONTO DA MISSÃO").strip().upper()

    tam_frase = 42 if len(nome_campanha) > 30 else 50
    fonte_frase = carregar_fonte(BOLD, tam_frase)
    linhas = quebrar_texto(nome_campanha, fonte_frase, W - 180, draw)

    box_y1 = 170
    altura_texto = len(linhas) * (tam_frase + 16)
    box_altura = max(220, altura_texto + 100)
    box_y2 = box_y1 + box_altura

    draw.rounded_rectangle(
        [(60, box_y1), (W - 60, box_y2)], radius=20,
        fill=BRANCO, outline="#FCA5A5", width=3,
    )
    draw.text(
        (W / 2, box_y1 + 38), f"LOCAL: {local_nome}",
        fill=VERMELHO, font=carregar_fonte(BOLD, 22), anchor="mm",
    )
    y0 = box_y1 + 75 + int((box_altura - 75 - altura_texto) / 2) + int(tam_frase / 2)
    for i, linha in enumerate(linhas):
        draw.text((W / 2, y0 + i * (tam_frase + 16)), linha, fill=PRETO, font=fonte_frase, anchor="mm")

    # 3. QR Code
    qr = qrcode.QRCode(
        version=None, error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=16, border=2,
    )
    qr.add_data(f"{BASE_URL}/e/{codigo}")
    qr.make(fit=True)
    qr_tam = 600
    qr_img = qr.make_image(fill_color="#111827", back_color="white").convert("RGB").resize((qr_tam, qr_tam))
    qr_x, qr_y = int((W - qr_tam) / 2), box_y2 + 40
    draw.rounded_rectangle(
        [(qr_x - 18, qr_y - 18), (qr_x + qr_tam + 18, qr_y + qr_tam + 18)],
        radius=22, fill=BRANCO, outline=CINZA_CLARO, width=2,
    )
    img.paste(qr_img, (qr_x, qr_y))

    # 4. Instruções
    y_inst = qr_y + qr_tam + 55
    draw.text((W / 2, y_inst), "Aponte a câmera do celular para o QR Code",
              fill=PRETO, font=carregar_fonte(BOLD, 32), anchor="mm")
    draw.text((W / 2, y_inst + 45), "Descubra o significado da frase e concorra a prêmios na KNN!",
              fill=CINZA, font=carregar_fonte(REGULAR, 24), anchor="mm")

    # 5. Rodapé
    draw.rectangle([(0, H - 110), (W, H)], fill="#F3F4F6")
    draw.line([(0, H - 110), (W, H - 110)], fill=CINZA_CLARO, width=2)

    local_nome = local["nome"] if local else "Ponto da Missão"
    parceiro = local["parceiro"] if local else None
    local_texto = f"Ponto: {local_nome}" + (f" · {parceiro}" if parceiro else "")
    if len(local_texto) > 45:
        local_texto = local_texto[:42] + "..."
    draw.text((60, H - 55), local_texto, fill=PRETO, font=carregar_fonte(BOLD, 20), anchor="lm")
    draw.text((W - 60, H - 55), f"Código: {codigo}", fill=CINZA, font=carregar_fonte(REGULAR, 20), anchor="rm")

    os.makedirs(QR_DIR, exist_ok=True)
    caminho = caminho_qr(codigo)
    img.save(caminho, quality=95)
    return caminho
