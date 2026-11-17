"""Ayudantes de Databricks usados por `gold()`: lectura de WTI, COMMENT y escritura de predicciones."""
from __future__ import annotations

from unittest.mock import Mock

from pipelines import databricks_layers

CFG = {"source": {"catalog": "workspace", "bronze_input": "s3://bucket-bronce/", "bronze_output": "s3://bucket-bronce/",
                  "silver_output": "s3://bucket-plata/", "gold_output": "s3://bucket-oro/"}}


def test_wti_ausente_devuelve_none_y_oro_sigue_sin_esa_variable():
    spark = Mock()
    spark.catalog.tableExists.return_value = False
    assert databricks_layers._read_wti(spark, CFG) is None
    spark.catalog.tableExists.assert_called_once_with("workspace.equipo7.bronze_petroleo_wti")
    spark.sql.assert_not_called()


def test_wti_se_convierte_a_double_sin_fallar_con_dias_vacios_en_modo_ansi():
    spark = Mock()
    spark.catalog.tableExists.return_value = True
    databricks_layers._read_wti(spark, CFG)
    consulta = spark.sql.call_args.args[0]
    # serverless usa ANSI: un CAST('' AS DOUBLE) lanzaría error; TRY_CAST deja nulo el día sin dato
    assert "TRY_CAST(" in consulta and "AS DOUBLE" in consulta and "DCOILWTICO" in consulta
    assert "workspace.equipo7.bronze_petroleo_wti" in consulta


def test_aplica_comentarios_a_la_tabla_administrada():
    spark = Mock()
    databricks_layers._apply_gold_comments(spark, CFG, "metricas_modelo")
    ejecutadas = [c.args[0] for c in spark.sql.call_args_list]
    assert ejecutadas[0].startswith("COMMENT ON TABLE workspace.equipo7.gold_metricas_modelo IS")
    assert any("ALTER COLUMN f1_macro_modelo COMMENT" in s for s in ejecutadas)


def test_rutas_de_las_tablas_nuevas_de_oro():
    assert databricks_layers._path(CFG, "gold", "predicciones") == "s3://bucket-oro/equipo7/predicciones"
    assert databricks_layers._table(CFG, "gold", "metricas_modelo") == "workspace.equipo7.gold_metricas_modelo"


def test_gold_orquesta_lectura_calculo_escritura_sincronizacion_y_comentarios(monkeypatch, tmp_path):
    import sys
    import types
    from unittest.mock import patch

    from gasolina_gt.gold.params import GoldParams
    from gasolina_gt.gold import pipeline, tracking  # carga sklearn antes de patch.dict(sys.modules)
    from tests.unit.gold_helpers import serie_alternante

    spark = Mock()
    silver = serie_alternante(30)
    spark.read.format.return_value.load.return_value.select.return_value.toPandas.return_value = silver
    spark.catalog.tableExists.return_value = False                      # sin WTI en Bronce
    delta_tables = types.ModuleType("delta.tables")
    delta_tables.DeltaTable = Mock()
    delta_tables.DeltaTable.isDeltaTable.side_effect = lambda _spark, path: path.endswith("/precios")  # sin predicciones previas
    escritas, sincronizadas, mezcladas = [], [], []
    monkeypatch.setattr(databricks_layers, "_spark", lambda: spark)
    monkeypatch.setattr(databricks_layers, "_ensure_layer_dir", lambda *a: None)
    monkeypatch.setattr(databricks_layers, "_write_gold_table",
                        lambda _s, _c, nombre, frame, mode="overwrite": escritas.append((nombre, mode, len(frame))))
    monkeypatch.setattr(databricks_layers, "_merge_predictions", lambda _s, _c, frame: mezcladas.append(len(frame)))
    monkeypatch.setattr(databricks_layers, "_sync_managed_table", lambda _s, _c, capa, nombre: sincronizadas.append((capa, nombre)))
    monkeypatch.setattr(tracking, "registrar_experimento", lambda *_args, **_kwargs: "run-de-prueba")
    cfg = {**CFG, "paths": {"reports": str(tmp_path)}}
    with patch.dict(sys.modules, {"delta": types.ModuleType("delta"), "delta.tables": delta_tables}):
        databricks_layers.gold(cfg, params=GoldParams())

    assert [n for n, _, _ in escritas] == ["precio_semanal", "variacion_semanal", "features_modelo", "metricas_modelo"]
    assert dict((n, m) for n, m, _ in escritas)["metricas_modelo"] == "append"   # historial de ejecuciones
    assert mezcladas and mezcladas[0] > 0
    assert sincronizadas == [("gold", n) for n in
                             ("precio_semanal", "variacion_semanal", "features_modelo", "predicciones", "metricas_modelo")]
    comentadas = {c.args[0].split("gold_")[1].split(" ")[0] for c in spark.sql.call_args_list
                  if c.args[0].startswith("COMMENT ON TABLE")}
    assert comentadas == {"precio_semanal", "variacion_semanal", "features_modelo", "predicciones", "metricas_modelo"}


def test_gold_falla_antes_de_escribir_si_mlflow_no_registra(monkeypatch):
    import sys
    import types
    from unittest.mock import patch

    from gasolina_gt.gold.params import GoldParams
    from gasolina_gt.gold import pipeline, tracking  # carga sklearn antes de patch.dict(sys.modules)
    from tests.unit.gold_helpers import serie_alternante

    spark = Mock()
    spark.read.format.return_value.load.return_value.select.return_value.toPandas.return_value = serie_alternante(30)
    spark.catalog.tableExists.return_value = False
    delta_tables = types.ModuleType("delta.tables")
    delta_tables.DeltaTable = Mock()
    delta_tables.DeltaTable.isDeltaTable.side_effect = lambda _spark, path: path.endswith("/precios")
    monkeypatch.setattr(databricks_layers, "_spark", lambda: spark)
    monkeypatch.setattr(databricks_layers, "_ensure_layer_dir", lambda *a: None)
    monkeypatch.setattr(tracking, "registrar_experimento", lambda *_args, **_kwargs: None)
    write = Mock()
    monkeypatch.setattr(databricks_layers, "_write_gold_table", write)
    with patch.dict(sys.modules, {"delta": types.ModuleType("delta"), "delta.tables": delta_tables}):
        try:
            databricks_layers.gold(CFG, params=GoldParams())
        except RuntimeError as exc:
            assert "MLflow no registró" in str(exc)
        else:
            raise AssertionError("Oro debió detenerse si MLflow falla")
    write.assert_not_called()
