# Titanic Entry Point Pipeline

Este paquete toma el pipeline de scikit-learn del notebook y lo expone como comandos instalables mediante entry points.

```bash
pip install -e .
titanic-train --help
titanic-train --model-path models/titanic_survival_pipeline.joblib
titanic-predict pasajeros.csv --model-path models/titanic_survival_pipeline.joblib
```

Los comandos se declaran en `[project.scripts]` dentro de `pyproject.toml`.
