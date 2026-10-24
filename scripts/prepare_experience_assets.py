"""Seleciona somente GLBs e texturas necessárias de três pacotes CC0 Kenney."""
import hashlib
import gzip
import io
import json
import pathlib
import re
import struct
import tempfile
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SELECTION = {
    "mini-characters": {"alex": "character-male-a.glb", "sam": "character-female-b.glb"},
    "furniture-kit": {
        "table": "tableRound.glb", "chair": "chair.glb", "counter": "kitchenBar.glb",
        "coffeeMachine": "kitchenCoffeeMachine.glb", "plant": "pottedPlant.glb",
        "bench": "benchCushion.glb", "bookcase": "bookcaseOpen.glb", "books": "books.glb",
        "reception": "desk.glb", "lamp": "lampRoundFloor.glb",
    },
    "food-kit": {"apple": "apple.glb", "coffee": "cup-coffee.glb", "sandwich": "sandwich.glb"},
}


def main():
    cache = pathlib.Path(tempfile.gettempdir()) / "knn-free-assets"
    cache.mkdir(exist_ok=True)
    manifest, records = {}, []
    for pack, selection in SELECTION.items():
        page = "https://kenney.nl/assets/" + pack
        html = urllib.request.urlopen(page, timeout=40).read().decode()
        links = re.findall(r"href=['\"]([^'\"]+\.zip[^'\"]*)['\"]", html)
        if not links or not links[0].startswith("https://kenney.nl/media/"):
            raise RuntimeError("Não foi encontrado um download oficial para " + pack)
        download = links[0]
        cached = cache / (pack + ".zip")
        if cached.exists():
            raw = cached.read_bytes()
        else:
            raw = urllib.request.urlopen(download, timeout=90).read(60 * 1024 * 1024)
            cached.write_bytes(raw)
        archive = zipfile.ZipFile(io.BytesIO(raw))
        license_name = next(n for n in archive.namelist() if n.lower() == "license.txt")
        license_text = archive.read(license_name).decode("utf-8-sig")
        if "CC0" not in license_text:
            raise RuntimeError("Confira a licença antes de continuar: " + pack)
        folder = ROOT / "static" / "experiences" / "assets" / ("kenney-" + pack + "-v1")
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "LICENSE.txt").write_text(license_text, encoding="utf-8")
        selected = []
        for key, filename in selection.items():
            name = next((n for n in archive.namelist() if n.endswith("/" + filename)), None)
            if not name:
                raise RuntimeError("Modelo não encontrado: " + filename)
            payload = archive.read(name)
            target = folder / filename
            target.write_bytes(payload)
            target.with_suffix(target.suffix + ".gz").write_bytes(gzip.compress(payload, mtime=0))
            size = struct.unpack_from("<I", payload, 12)[0]
            gltf = json.loads(payload[20:20 + size])
            for image in gltf.get("images", []):
                uri = image.get("uri", "")
                if uri and not uri.startswith("data:"):
                    texture = pathlib.PurePosixPath(uri)
                    if texture.is_absolute() or ".." in texture.parts:
                        raise RuntimeError("Caminho de textura inválido")
                    original = str(pathlib.PurePosixPath(name).parent / texture)
                    destination = folder.joinpath(*texture.parts)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(archive.read(original))
            version = hashlib.md5(hashlib.md5(payload).hexdigest().encode()).hexdigest()[:10]
            manifest[key] = "/static/experiences/assets/" + folder.name + "/" + filename + "?v=" + version
            selected.append(dict(key=key, file=filename, bytes=len(payload),
                                 sha256=hashlib.sha256(payload).hexdigest(),
                                 animations=[a.get("name") for a in gltf.get("animations", [])]))
        records.append(dict(author="Kenney", pack=pack, source=page, download=download,
                            license="CC0", archive_sha256=hashlib.sha256(raw).hexdigest(),
                            selected=selected))
    target = ROOT / "frontend" / "experiences"
    target.mkdir(parents=True, exist_ok=True)
    (target / "assets.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    docs = ROOT / "docs" / "planejamento"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "RECURSOS.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Recursos selecionados:", sum(len(r["selected"]) for r in records))
    print("Bytes GLB:", sum(s["bytes"] for r in records for s in r["selected"]))


if __name__ == "__main__":
    main()
