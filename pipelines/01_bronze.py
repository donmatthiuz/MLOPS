"""Bronce: archivo de origen local o binaryFile sobre external location."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from common import settings


def main() -> None:
    cfg = settings()
    if cfg["source"]["mode"] == "databricks":
        from databricks_layers import bronze
        bronze(cfg)
        return
    from gasolina_gt.config import resolve_path

    source = resolve_path(cfg["paths"]["datos_raw"])
    destination = resolve_path(cfg["paths"]["bronze"])
    destination.mkdir(parents=True, exist_ok=True)
    images = sorted(path for path in source.iterdir() if path.is_file() and path.suffix.lower() in {".heic", ".jpg", ".jpeg", ".png"})
    manifest_path = destination / "fotos_precios.json"
    previous = {row["path"]: row for row in json.loads(manifest_path.read_text(encoding="utf-8"))} if manifest_path.exists() else {}
    manifest = []
    for path in images:
        entry = {"path": str(path.resolve()), "length": path.stat().st_size,
                 "modificationTime": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
                 "_source_file": str(path.resolve())}
        old = previous.get(entry["path"])
        entry["_ingestion_timestamp"] = old["_ingestion_timestamp"] if old and "_ingestion_timestamp" in old and old["length"] == entry["length"] and old["modificationTime"] == entry["modificationTime"] else datetime.now(timezone.utc).isoformat()
        manifest.append(entry)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Bronce local: {len(images)} fotos en {destination}")


if __name__ == "__main__":
    main()
