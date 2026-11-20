# Despliegue de la API en el Droplet · equipo 7

Referencia: [enunciado](enunciado_proyecto.pdf), fase 5, y sección «API en DigitalOcean» del [README](../README.md). Contrato de datos: [docs/oro/contrato_api.md](oro/contrato_api.md).

## Estado del despliegue

Actualizado el 17 de noviembre de 2026.

| Requisito de la fase 5 | Estado |
| --- | --- |
| Acceso por SSH al Droplet | Hecho con el usuario `cc3105-02` en `cc3105-pf-02` (IP pública `159.65.111.14`) |
| Dependencias aisladas con Docker | Hecho: imagen `equipo07-gasolina-api-api` construida en el Droplet desde `~/MLOPS` (rama `proyecto1`) |
| API en el puerto 80XX | Hecho: `http://159.65.111.14:8007/docs` responde 200 desde una computadora externa |
| Sigue corriendo al cerrar SSH | Configurado con `restart: unless-stopped` |
| Endpoints con datos de Oro | **Bloqueado**: falta permiso de lectura en S3 (ver la sección siguiente). Mientras tanto `/health` responde 503 y el contenedor aparece `unhealthy` |

Comprobaciones locales previas:

- `tests/integration/test_api.py`: 4 pruebas correctas.
- El contenedor, con las mismas restricciones de `compose.yaml` (`read_only`, `cap_drop: ALL`, `no-new-privileges`), se probó contra un S3 local (MinIO) con tablas Delta de Oro de ejemplo. `tests/consultas_api.sh` respondió en todos los endpoints y `/docs` devolvió 200.
- Sin `AWS_ACCESS_KEY_ID` y `AWS_SECRET_ACCESS_KEY` en el entorno del contenedor, `/health` devuelve 503. Las credenciales de `~/.aws` del usuario Linux no se heredan.
- La interfaz React se compila en la misma imagen y se abre en `/` por el puerto de la API. Puede cargar sin S3 y muestra que Oro no está disponible; los precios y pronósticos requieren el permiso pendiente.
- La API lee los Delta con `DeltaTable.scan`, compatible con la función `deletionVectors` que Databricks activó en las tablas Oro. `/health` comprueba también una lectura inicial para detectar fallos del lector.

## Bloqueo: lectura de Oro en S3

La API debe leer el prefijo completo configurado en `GOLD_OUTPUT_URI`, que debe coincidir con `gold_output_uri` del Job `equipo-07-pipeline`. El Job debe ejecutarse de nuevo si se cambia ese prefijo, para generar las cinco tablas allí. Databricks escribe con su storage credential de Unity Catalog, que no se puede usar desde el Droplet.

Diagnóstico en el Droplet (solo lectura):

- Las únicas credenciales del usuario `cc3105-02` son del usuario IAM `cc3105-equipo7`. Los perfiles `[default]` y `[cc3105-equipo7]` de `~/.aws/credentials` y `~/.aws/env/cc3105-equipo7.env` tienen las mismas llaves. No hay `role_arn` ni `source_profile`.
- `~/.aws/env/cc3105-equipo7.env` define `S3_BUCKET=cc3105-cusn-869227452861-us-east-2-an`, `S3_PREFIX=cc3105-equipo7/monitoreo` y `SYNC_INTERVAL=300`: el usuario fue creado para el monitoreo del curso, no para la API.
- `s3:ListBucket` da `AccessDenied` ("no identity-based policy allows") en los buckets `cc3105-raw`, `cc3105-cusn`, `cc3105-ag` y `cc3105-au`, en la raíz y en los prefijos `equipo7/`, `equipo-07/` y `cc3105-equipo7/`. `s3:ListAllMyBuckets` y la consulta de sus políticas IAM también se deniegan.

Conclusión: el equipo no puede resolverlo por su cuenta. La solicitud de lectura del 17 de noviembre mencionaba el prefijo anterior `equipo7/`; si se cambia, hay que pedir `s3:ListBucket` y `s3:GetObject` para el prefijo completo elegido en `gold_output_uri`, o credenciales de solo lectura para la API. `deltalake` necesita listar `_delta_log`, así que `s3:GetObject` solo no basta.

## Cuando llegue el permiso

En el Droplet, como `cc3105-02`:

```bash
cd ~/MLOPS
git pull
aws s3 ls s3://bucket-oro/prefijo-completo/   # sustituir por gold_output_uri; deben verse las cinco tablas
nano api/.env            # agregar AWS_ACCESS_KEY_ID y AWS_SECRET_ACCESS_KEY
docker compose --env-file api/.env up -d --build
docker compose --env-file api/.env ps                         # esperar "healthy"
API_URL=http://localhost:8007 sh tests/consultas_api.sh
```

Si el permiso se agrega al mismo usuario `cc3105-equipo7`, las llaves se pueden copiar a `api/.env` sin escribirlas a mano:

```bash
k() { awk -F' *= *' -v key="$1" '/^\[/{s=$0} s=="[cc3105-equipo7]" && $1==key{print $2}' ~/.aws/credentials; }
printf 'AWS_ACCESS_KEY_ID=%s\nAWS_SECRET_ACCESS_KEY=%s\n' "$(k aws_access_key_id)" "$(k aws_secret_access_key)" >> api/.env
```

Después, completar la [prueba externa](#prueba-desde-una-computadora-externa) y la [evidencia](#evidencia-para-el-informe).

## Datos que hay que reunir

| Dato | Dónde obtenerlo |
| --- | --- |
| IP del Droplet y llave SSH | Accesos entregados al equipo. El Droplet lo comparten todos los equipos; el equipo 7 usa el usuario Linux `cc3105-02` |
| `GOLD_OUTPUT_URI` | Databricks: `Jobs & Pipelines → equipo-07-pipeline → Job parameters → gold_output_uri`, o `Catalog → External locations` |
| `AWS_ACCESS_KEY_ID` y `AWS_SECRET_ACCESS_KEY` de solo lectura | Las que indique el catedrático; el perfil `[cc3105-equipo7]` del Droplet no tiene lectura sobre Oro por ahora |
| Puerto | `8007` (convención `80XX`) |

## Pasos en el Droplet

Pasos completos para una instalación desde cero. Los pasos 1, 3 y 5 ya se hicieron; el 2 y el 4 esperan el permiso de S3.

1. Entrar por SSH:

   ```bash
   ssh -i <llave> cc3105-02@<ip>
   cd ~
   ```

2. Comprobar las herramientas y el acceso a Oro antes de tocar Docker:

   ```bash
   docker ps                         # debe responder sin sudo
   docker compose version
   aws sts get-caller-identity --profile cc3105-equipo7
   aws s3 ls s3://bucket-oro/prefijo-completo/ --profile cc3105-equipo7   # sustituir por gold_output_uri
   ```

   Si `aws s3 ls` no muestra las cinco carpetas, el problema está en la URI o en las credenciales, no en la API. `docker ps` muestra también los contenedores de otros equipos: no detenerlos ni borrarlos.

3. Clonar o actualizar el repositorio:

   ```bash
   git clone -b proyecto1 https://github.com/donmatthiuz/MLOPS.git   # primera vez
   cd MLOPS
   git pull                                                          # veces siguientes
   ```

4. Crear el `.env` solo en el servidor:

   ```bash
   cp api/.env.example api/.env
   chmod 600 api/.env
   nano api/.env   # completar GOLD_OUTPUT_URI, API_PORT y las dos llaves AWS
   ```

5. Construir y levantar:

   ```bash
   docker compose --env-file api/.env up -d --build
   docker compose --env-file api/.env ps     # esperar STATUS "healthy"
   curl http://localhost:8007/health
   API_URL=http://localhost:8007 sh tests/consultas_api.sh
   ```

6. Comprobar que sigue corriendo al cerrar SSH: salir, volver a entrar y repetir `docker compose --env-file api/.env ps`. `restart: unless-stopped` también la levanta tras reiniciar el Droplet.

## Prueba desde una computadora externa

Desde la computadora propia, no desde el Droplet:

```bash
curl http://<ip>:8007/health
API_URL=http://<ip>:8007 sh tests/consultas_api.sh
```

Abrir `http://<ip>:8007/` para la interfaz y `http://<ip>:8007/docs` para Swagger. Esta es la prueba del criterio de aceptación.

## Evidencia para el informe

- Salida de `docker compose --env-file api/.env ps` con el contenedor `healthy`.
- Salida de `tests/consultas_api.sh` ejecutado desde una computadora externa.
- Captura de Swagger en `/docs`.
- Captura de `/prediccion` para `super`, `regular` y `diesel`.

No incluir en capturas ni commits el contenido de `api/.env`.

## Si algo falla

| Síntoma | Causa probable | Qué revisar |
| --- | --- | --- |
| `/health` responde 503 | Credenciales, URI o región | `docker compose --env-file api/.env logs --tail=100 api`; comparar con `aws s3 ls <GOLD_OUTPUT_URI>` |
| `/health` OK pero un endpoint da 503 | La tabla existe pero no se pudo leer | Logs; si mencionan `deletionVectors`, actualizar el repositorio y reconstruir la imagen para usar `DeltaTable.scan` |
| `/prediccion` o `/modelo/metricas` dan 404 | Oro no generó pronóstico o métricas | Ejecutar el Job en Databricks y revisar `gold_predicciones` y `gold_metricas_modelo` |
| Funciona en el Droplet pero no desde fuera | Firewall o puerto | Puerto asignado correcto en `API_PORT`; consultar al catedrático si el 8007 está abierto |
| `docker ps` pide permisos | El usuario no está en el grupo `docker` | Pedir acceso al catedrático; no usar `sudo` sobre recursos de otros equipos |

Para actualizar después de un cambio de código: `git pull` y `docker compose --env-file api/.env up -d --build`. Para detenerla: `docker compose --env-file api/.env down`.
