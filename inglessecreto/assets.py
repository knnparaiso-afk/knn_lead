import gzip
import os

ASSET_VERSION = "20261016.6"


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


def register(app):
    app.template_filter("v")(versioned_asset)
    garantir_modelos_comprimidos(app)
