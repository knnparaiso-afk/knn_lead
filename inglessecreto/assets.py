import gzip
import os

ASSET_VERSION = "20261017.2"


def versioned_asset(url):
    """Adiciona parâmetro de versão para cache-busting de assets."""
    if not url:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}v={ASSET_VERSION}"


def garantir_modelos_comprimidos(app):
    """Gera .glb.gz pré-comprimidos (gzip nível 9) para economizar banda."""
    try:
        models_dir = os.path.join(app.root_path, "static", "models")
        if not os.path.isdir(models_dir):
            return
        for root, _dirs, files in os.walk(models_dir):
            for f in files:
                if f.lower().endswith(".glb"):
                    raw_path = os.path.join(root, f)
                    gz_path = raw_path + ".gz"
                    if not os.path.exists(gz_path) or os.path.getmtime(raw_path) > os.path.getmtime(gz_path):
                        with open(raw_path, "rb") as f_in, gzip.open(gz_path, "wb", compresslevel=9) as f_out:
                            f_out.write(f_in.read())
    except Exception:
        app.logger.exception("Falha ao pré-comprimir modelos 3D")


def formatar_data_brasil(valor):
    """Formata timestamps ISO/SQL para formato amigável brasileiro (dd/mm/aaaa às HH:MM)."""
    if not valor:
        return "—"
    try:
        texto = str(valor).strip()
        # Remove microssegundos se existirem
        if "." in texto:
            texto = texto.split(".")[0]
        # Trata formato YYYY-MM-DD HH:MM:SS ou YYYY-MM-DDTHH:MM:SS
        texto = texto.replace("T", " ")
        if len(texto) >= 16:
            partes = texto.split(" ")
            data_pts = partes[0].split("-")
            hora_pts = partes[1].split(":")
            if len(data_pts) == 3 and len(hora_pts) >= 2:
                ano, mes, dia = data_pts
                hora, minuto = hora_pts[0], hora_pts[1]
                return f"{dia}/{mes}/{ano} às {hora}:{minuto}"
        elif len(texto) == 10 and "-" in texto:
            ano, mes, dia = texto.split("-")
            return f"{dia}/{mes}/{ano}"
        return texto
    except Exception:
        return str(valor)


def register(app):
    app.template_filter("v")(versioned_asset)
    app.template_filter("data_br")(formatar_data_brasil)
    garantir_modelos_comprimidos(app)
