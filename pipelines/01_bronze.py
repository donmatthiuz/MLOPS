# Databricks notebook source
"""Bronce: archivo de origen local o binaryFile sobre external location."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def _setup_imports() -> None:
    candidates = [Path.cwd(), Path.cwd() / "pipelines"]
    if "__file__" in globals():
        candidates.insert(0, Path(__file__).resolve().parent)
    if "dbutils" in globals():
        notebook = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
        path = Path(notebook if notebook.startswith("/Workspace/") else "/Workspace" + notebook)
        candidates.insert(0, path.parent)
    for directory in candidates:
        if (directory / "common.py").is_file() and (directory.parent / "src" / "gasolina_gt").is_dir():
            sys.path[:0] = [str(directory), str(directory.parent / "src")]
            return
    raise RuntimeError("No se encontró pipelines/common.py y src/gasolina_gt en el Git folder")


_setup_imports()
from common import job_settings, settings


def main() -> None:
    cfg = job_settings(dbutils.widgets) if "dbutils" in globals() else settings()
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
