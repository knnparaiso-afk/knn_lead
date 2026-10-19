"""Servidor de modelos 3D com gzip pré-comprimido."""
import mimetypes
import os

from flask import Blueprint, current_app, make_response, request, send_file

bp = Blueprint("models", __name__)

@bp.route("/static/models/<path:filename>")
def servir_modelo_estatico(filename):
    models_dir = os.path.realpath(os.path.join(current_app.root_path, "static", "models"))
    safe_path = os.path.realpath(os.path.join(models_dir, filename))
    # commonpath evita o bypass de prefixo (".../models_evil") do startswith
    if os.path.commonpath([safe_path, models_dir]) != models_dir:
        return ("Arquivo não encontrado", 404)

    gz_path = safe_path + ".gz"
    if "gzip" in request.headers.get("Accept-Encoding", "") and os.path.isfile(gz_path):
        response = make_response(send_file(gz_path, mimetype="model/gltf-binary"))
        response.headers["Content-Encoding"] = "gzip"
        response.headers["Vary"] = "Accept-Encoding"
        return response

    if os.path.isfile(safe_path):
        if safe_path.lower().endswith(".glb"):
            mime = "model/gltf-binary"
        else:
            mime = mimetypes.guess_type(safe_path)[0] or "application/octet-stream"
        response = make_response(send_file(safe_path, mimetype=mime))
        response.headers["Vary"] = "Accept-Encoding"
        return response

    return ("Modelo não encontrado", 404)


@bp.route("/models/<path:filename>")
def servir_modelos(filename):
    """Compatibilidade com URLs legadas."""
    return servir_modelo_estatico(filename)
