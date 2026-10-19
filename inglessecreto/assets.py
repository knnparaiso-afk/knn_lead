import gzip
import hashlib
import os
import re

ASSET_VERSION = "20261017.5"  # fallback, só usado se o arquivo não for encontrado

_cache_versoes = {}


def _hash_arquivo(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for bloco in iter(lambda: f.read(65536), b""):
            h.update(bloco)
    return h.hexdigest()


def _versao_do_arquivo(url_path):
    """Versão automática do conteúdo, recalculada se o arquivo mudar."""
    from flask import current_app

    try:
        static_dir = current_app.static_folder
        rel = url_path.split("/static/", 1)[1]
        arquivo = os.path.join(static_dir, *rel.split("/"))
        stat = os.stat(arquivo)
        assinatura = (stat.st_mtime_ns, stat.st_size)
        cached = _cache_versoes.get(url_path)
        if cached and cached[0] == assinatura:
            return cached[1]
        versao = hashlib.md5(_hash_arquivo(arquivo).encode()).hexdigest()[:10]
        _cache_versoes[url_path] = (assinatura, versao)
        return versao
    except (OSError, IndexError):
        return ASSET_VERSION


def asset_tem_versao_atual(url_path, versao):
    """Só permite cache imutável quando ?v corresponde ao arquivo servido."""
    from flask import current_app

    if not re.fullmatch(r"[0-9a-f]{10}", versao or ""):
        return False
    if not url_path.startswith("/static/"):
        return False
    static_dir = os.path.realpath(current_app.static_folder)
    rel = url_path[len("/static/"):]
    arquivo = os.path.realpath(os.path.join(static_dir, *rel.split("/")))
    try:
        if os.path.commonpath((static_dir, arquivo)) != static_dir:
            return False
        return os.path.isfile(arquivo) and versao == _versao_do_arquivo(url_path)
    except ValueError:
        return False


def versioned_asset(url):
    """Adiciona ?v=<hash do arquivo> para cache-busting automático de assets."""
    if not url:
        return url
    path_only = url.split("?", 1)[0]
    versao = _versao_do_arquivo(path_only) if "/static/" in path_only else ASSET_VERSION
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}v={versao}"


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
