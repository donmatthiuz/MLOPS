# Gasolina GT

Proyecto CRISP-DM para extraer precios de combustible desde fotografías, construir un histórico y recomendar si conviene recargar ahora.

## Uso

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
gasolina-gt build-data
gasolina-gt train --combustible regular
gasolina-gt recommend --combustible regular --horizonte 1 --hora 18
uvicorn gasolina_gt.serving.api:app --reload
```

La API expone `GET /health` y `GET /recomendacion?combustible=regular&horizonte=1&hora=18`.

## Docker Compose

Inicia la preparación de datos y el entrenamiento una vez, y luego publica la API en `http://localhost:8000`:

```bash
docker compose up --build
```

Consulta la recomendación:

```bash
curl 'http://localhost:8000/recomendacion?combustible=regular&horizonte=1&hora=18'
```

Para correr las pruebas dentro del contenedor:

```bash
docker compose run --rm tests
```

Para ejecutar operaciones manuales sobre los artefactos persistentes:

```bash
docker compose run --rm cli recommend --combustible regular --horizonte 1 --hora 18
docker compose run --rm cli train --combustible regular
```

Para reiniciar completamente el pipeline y eliminar los datos/modelos generados:

```bash
docker compose down --volumes
```

## Nota de validez

El modelo usa división temporal y se compara con persistencia. Si Bronze/Silver no contiene lecturas reales válidas, Gold se genera con observaciones sintéticas calibradas por la fuente externa. En ese caso el resultado lleva una advertencia y **no constituye validación de campo**; deben añadirse/prevalidarse fotografías reales antes de tomar decisiones de alto impacto.
