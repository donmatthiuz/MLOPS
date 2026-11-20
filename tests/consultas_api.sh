#!/usr/bin/env sh
# Ejecutar desde una computadora externa: API_URL=http://<ip>:<puerto> sh tests/consultas_api.sh
set -eu
API_URL="${API_URL:-http://localhost:8007}"

curl --fail --show-error --silent --output /dev/null "$API_URL/"
printf 'Frontend: OK\n'
curl --fail --show-error --silent "$API_URL/health"
printf '\n'
curl --fail --show-error --silent "$API_URL/precios/actual"
printf '\n'
curl --fail --show-error --silent "$API_URL/modelo/metricas"
printf '\n'
for combustible in super regular diesel; do
    curl --fail --show-error --silent "$API_URL/precios?combustible=$combustible&limit=3"
    printf '\n'
    curl --fail --show-error --silent "$API_URL/prediccion?combustible=$combustible"
    printf '\n'
done
