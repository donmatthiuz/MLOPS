"""La API debe poder leer los Delta creados con deletion vectors en Databricks."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pyarrow as pa
from deltalake import DeltaTable, write_deltalake

from api.app import gold_store


class DeltaReaderTests(unittest.TestCase):
    def test_lee_tabla_con_reader_feature_deletion_vectors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            write_deltalake(directory, pa.table({
                "semana": ["2026-11-10", "2026-11-17"],
                "precio_promedio": [34.5, 35.0],
            }))
            log = Path(directory) / "_delta_log" / "00000000000000000000.json"
            actions = [json.loads(line) for line in log.read_text().splitlines()]
            for action in actions:
                if "protocol" in action:
                    action["protocol"] = {
                        "minReaderVersion": 3,
                        "minWriterVersion": 7,
                        "readerFeatures": ["deletionVectors"],
                        "writerFeatures": ["deletionVectors"],
                    }
                if "metaData" in action:
                    action["metaData"].setdefault("configuration", {})["delta.enableDeletionVectors"] = "true"
            log.write_text("\n".join(json.dumps(action) for action in actions) + "\n")

            table = DeltaTable(directory)
            with patch.object(gold_store, "_delta_table", return_value=table):
                rows = gold_store.read_gold("precio_semanal", ["semana", "precio_promedio"])
                gold_store.check_gold()

            self.assertEqual(sorted(rows, key=lambda row: row["semana"]), [
                {"semana": "2026-11-10", "precio_promedio": 34.5},
                {"semana": "2026-11-17", "precio_promedio": 35.0},
            ])
