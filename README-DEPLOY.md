# Signify Python private deployment

## Architecture and files

React → Spring Boot → `http://signify-python:8000` → Flask/ONNX → Spring Boot → React. Python has no public domain, Traefik route or host port. Gunicorn binds `0.0.0.0:8000` **inside** the container to accept internal traffic.

Push to `main` → GitHub Actions CI → Docker Hub (SHA and `latest`) → Dokploy Compose → VPS. The workflow uses the documented [Dokploy Compose API](https://docs.dokploy.com/docs/api/compose): `POST /api/compose.deploy` with `x-api-key` and JSON `composeId`.

Files: `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `.env.example`, `.github/workflows/deploy.yml`, this guide, and updated `requirements.txt`. MediaPipe is pinned at 0.10.21 for the `solutions` API used by source. `api.py` is unchanged.

## Private network

Use a dedicated attachable overlay network `signify-private` on the **same Docker Swarm** as Spring Boot. Dokploy remote servers are independent Docker environments; DNS across them does not work automatically. Inspect the existing backend service first:

```bash
docker info --format '{{.Swarm.LocalNodeState}}'
docker network ls
docker service ls
docker service inspect SPRING_BOOT_SERVICE --format '{{json .Spec.TaskTemplate.Networks}}'
```

On the VPS hosting both services, create the network once:

```bash
docker network create --driver overlay --attachable signify-private
```

`docker-compose.yml` declares this network as `external` and gives Python the alias `signify-python`. Attach the Spring Boot service to the same network through its **persistent Dokploy configuration/deployment definition**. A one-off `docker service update --network-add signify-private SPRING_BOOT_SERVICE` may be overwritten by Dokploy and may roll backend tasks, so coordinate that step with the backend owner. Do not alter React. Disable Dokploy Compose **Isolated Deployments** for this service to prevent network rewriting. Do not set a domain or published port. [Dokploy network behavior](https://docs.dokploy.com/docs/core/docker-compose/utilities) must be considered for the installed version.

`http://signify-python:8000` is valid only after both services join this network and DNS works from Spring Boot. If backend networking cannot be changed safely, pause integration and choose another approved private connection; do not expose Python publicly.

## Model on VPS

The ONNX model is Git ignored and Docker ignored. Upload from PowerShell; do not replace an existing model without preserving it:

```powershell
scp .\asl_cnn_model.onnx USER@103.72.57.116:/tmp/asl_cnn_model.onnx
```

On the VPS:

```bash
sudo install -d -m 755 /opt/signify/models
sudo install -m 644 /tmp/asl_cnn_model.onnx /opt/signify/models/asl_cnn_model.onnx
test -s /opt/signify/models/asl_cnn_model.onnx
```

Compose mounts that file read-only at `/app/asl_cnn_model.onnx`. The image runs as UID 10001; file mode 644 and traversable parent directories allow it to read the model. Startup checks that the file is readable and nonempty before Gunicorn starts. Ensure the file is on the actual node running Python.

## GitHub and Dokploy configuration

Create a Docker Hub repository and configure these in **this GitHub repository**:

| Name | Type | Purpose |
|---|---|---|
| `DOCKERHUB_USERNAME` | Secret | Registry login |
| `DOCKERHUB_TOKEN` | Secret | Push token |
| `DOKPLOY_URL` | Secret | Dokploy HTTPS base URL |
| `DOKPLOY_API_KEY` | Secret | Deploy API key |
| `DOKPLOY_COMPOSE_ID` | Secret | ID of the **Python Compose** deployment |
| `DOCKERHUB_IMAGE_REPOSITORY` | Variable | `namespace/repository`, no tag |

`DOCKERHUB_REGISTRY` is unnecessary for the default Docker Hub registry. `DOKPLOY_APPLICATION_ID` must not be used for this Compose deployment. Secrets from the backend GitHub repository are not shared automatically.

In Dokploy, create a **Docker Compose** service using this repository's `docker-compose.yml`. Set `SIGNIFY_PYTHON_IMAGE=namespace/repository:latest` and optionally `SIGNIFY_MODEL_PATH=/opt/signify/models/asl_cnn_model.onnx` as Compose environment variables. Use the same image repository that CI pushes. Configure registry pull credentials if private. Set no domain, no port publication, and disable Isolated Deployments. Copy its Compose ID to `DOKPLOY_COMPOSE_ID`. The deployment API accepting a trigger does not prove the service became healthy; inspect Dokploy deployment status afterwards.

## Spring Boot integration and connectivity

The Python repository cannot prove Spring Boot currently reads `PYTHON_SERVICE_URL`. Add it to the backend repository if absent and configure `PYTHON_SERVICE_URL=http://signify-python:8000`. The backend HTTP client needs connection/read timeouts and should forward meaningful errors. User authentication remains in Spring Boot.

After networking is configured, test **from the Spring Boot container**:

```bash
getent hosts signify-python
curl --fail --show-error http://signify-python:8000/health
curl --fail --show-error -F 'image=@hand.jpg' http://signify-python:8000/api/v1/predict
```

Use the backend's HTTP client or a diagnostic container on the same network if `curl` is unavailable. Check `docker service inspect`/`docker ps` to confirm port 8000 is not published on the host. Do not infer Spring Boot connectivity from Python's own healthcheck.

## Build, operations and rollback

```bash
docker build -t signify-python:local .
```

For standalone local Compose, create `signify-private` locally (`docker network create signify-private` on a non-Swarm engine), copy `.env.example` to `.env`, set an actual model path, and set `SIGNIFY_PYTHON_IMAGE=signify-python:local` to use the local image. Then run:

```bash
docker compose config
docker compose up -d
docker compose ps
docker compose logs -f signify-python
```

Use Dokploy logs or `docker compose logs` for startup errors. `/health` checks the HTTP process after model startup; it does not run inference. Prediction accepts multipart field `image`: 200 for a confident result, 400 for invalid input, 413 above 10 MiB and 422 for no hand/low confidence. The single Gunicorn worker holds one model copy; two threads share the inference lock. Its 60-second timeout is an initial operational setting.

For rollback, use a previously healthy SHA image tag in Dokploy and redeploy. Restore the prior model too if it changed. The mutable `latest` tag alone cannot identify an exact previous build. Python CORS is unnecessary because React never calls it. If untrusted containers join the private network, add service-to-service authentication. The 10 MiB request limit does not bound decoded pixel dimensions; monitor CPU/RAM and add dimension limits if needed.
