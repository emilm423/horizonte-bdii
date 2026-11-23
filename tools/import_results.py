"""Importa artefactos propios de Colab. Publica freeze.json después de verificar pesos y datos."""

import argparse
import json
import os
import tempfile
import zipfile
from pathlib import Path

from core.data import SYMBOLS, file_hash, validate_catalog


def install(archive_path, root):
    root = Path(root).resolve()
    (root / "data").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="import_", dir=root / "data") as temporary:
        staging = Path(temporary)
        with zipfile.ZipFile(archive_path) as archive:
            names = set()
            total = 0
            for member in archive.infolist():
                path = Path(member.filename)
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or not path.parts
                    or path.parts[0] not in ("artifacts", "data")
                ):
                    raise ValueError("El ZIP contiene una ruta no permitida.")
                if path.parts[0] == "data" and (
                    len(path.parts) < 2 or path.parts[1] != "raw"
                ):
                    raise ValueError("Solo se permite data/raw además de artifacts.")
                if member.filename in names:
                    raise ValueError("El ZIP contiene rutas repetidas.")
                names.add(member.filename)
                total += member.file_size
                if member.file_size > 500_000_000 or total > 3_000_000_000:
                    raise ValueError("Tamaño de importación fuera de límites.")
            archive.extractall(staging)
        catalog = staging / "artifacts" / "asset_catalog.json"
        selected_symbols = validate_catalog(json.loads(catalog.read_text())) if catalog.exists() else SYMBOLS
        for symbol in selected_symbols:
            directory = staging / "artifacts" / symbol
            if (directory / "freeze.json").exists():
                frozen = json.loads((directory / "freeze.json").read_text())
                if file_hash(directory / "processed.csv") != frozen["source_sha256"]:
                    raise ValueError(f"{symbol}: hash del dataset incorrecto.")
                selected = frozen["selected"]
                model_dir = (directory / selected["directory"]).resolve()
                if not model_dir.is_relative_to(directory.resolve()):
                    raise ValueError("Ruta de modelo inválida.")
                if selected["kind"] != "Zero":
                    model = model_dir / (
                        "model.joblib"
                        if selected["kind"] == "Linear"
                        else "model.keras"
                    )
                    if (
                        file_hash(model) != frozen["model_sha256"]
                        or file_hash(model_dir / "scalers.joblib")
                        != frozen["scalers_sha256"]
                    ):
                        raise ValueError(
                            f"{symbol}: hash de modelo o escalador incorrecto."
                        )
        files = [path for path in staging.rglob("*") if path.is_file()]
        for source in files:
            target = root / source.relative_to(staging)
            if target.exists() and file_hash(target) != file_hash(source):
                raise ValueError(
                    f"{target.relative_to(root)} ya existe con contenido distinto. Usar una copia nueva del proyecto."
                )
        # Primero datos y modelos. Una nueva carpeta solo se habilita cuando su freeze se publica al final.
        files.sort(key=lambda path: (path.name == "asset_catalog.json", path.name == "freeze.json"))
        for source in files:
            target = root / source.relative_to(staging)
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(source, target)
    print("Artefactos propios importados y hashes verificados. Reinicia el backend para cargar el catálogo de activos.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("zip")
    args = parser.parse_args()
    install(args.zip, Path(__file__).resolve().parents[1])
