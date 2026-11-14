#!/usr/bin/env sh
# Prueba de humo de la API local actual. Requiere entrenar el modelo Regular.
set -eu
API_URL="${API_URL:-http://localhost:8000}"
curl --fail --show-error --silent "$API_URL/health"
printf '\n'
curl --fail --show-error --silent "$API_URL/recomendacion?combustible=regular&horizonte=1"
printf '\n'
