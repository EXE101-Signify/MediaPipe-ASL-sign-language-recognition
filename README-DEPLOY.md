# Signify Python deployment: GitHub → Dokploy

## Architecture

Push to `main` → GitHub Actions CI → Dokploy Application deployment API → Dokploy clones `main` → Dokploy builds `Dockerfile` → VPS runs the Python container. Pull requests to `main` run CI without deployment. React calls Spring Boot; Spring Boot calls Python internally. Python has no public domain or published host port.

The repository includes `Dockerfile`, `.dockerignore`, `.github/workflows/deploy.yml`, and this guide. `docker-compose.yml` and `.env.example` are **local testing only**. Compose is not the Dokploy production source. `requirements.txt` contains inference/API dependencies; `requirements-train.txt` is not installed in the image. The runtime is Python 3.11 slim, Gunicorn factory `api:create_app()`, one worker/two threads, port 8000. The image runs as UID 10001.

## Dokploy Application `sign-language`

Edit the existing Application; do not create a Compose deployment. Set Source Provider to GitHub, connect a GitHub Provider/App with access to this repository if necessary, select the Python repository and branch `main`. Set Build Type to Dockerfile, Root Directory to repository root (`/` in Dokploy), Dockerfile Path to `Dockerfile`, build context to repository root, and container port to `8000`. Dokploy [documents Dockerfile builds](https://docs.dokploy.com/docs/core/applications/build-type) and the [Application deployment API](https://docs.dokploy.com/docs/api/application).

Disable Dokploy GitHub auto deploy/webhook for this Application so an untested push cannot trigger a separate build. The GitHub Actions deploy job is the sole trigger after CI passes. Do not assign a domain or configure a published host port. Keep the Application on the same Docker environment as Spring Boot. Confirm the existing Application ID before populating the GitHub secret; changing the Source on the existing Application should preserve its ID, but verify it in Dokploy.

## ONNX model mount

`asl_cnn_model.onnx` is Git ignored and Docker ignored. The image does not include it. Upload the chosen trained model from Windows:

```powershell
scp .\asl_cnn_model.onnx USER@YOUR_VPS:/tmp/asl_cnn_model.onnx
```

On the VPS, preserve any previous model before replacing it, then install the uploaded file:

```bash
sudo install -d -m 755 /opt/signify/models
sudo install -m 644 /tmp/asl_cnn_model.onnx /opt/signify/models/asl_cnn_model.onnx
test -s /opt/signify/models/asl_cnn_model.onnx
```

In Dokploy Application Volumes, add a **Bind Mount** with Host Path `/opt/signify/models/asl_cnn_model.onnx` and Mount Path `/app/asl_cnn_model.onnx`; set read-only if supported. Choose Bind Mount, not Dokploy's File Mount, because File Mount stores content managed by Dokploy. The model must exist on the node running this Application. UID 10001 must be able to traverse parent directories and read the file. The startup command checks readability and nonempty content, then `api.py` loads it from `/app/asl_cnn_model.onnx`. `class_names.txt` is copied into the image.

## GitHub Actions and secrets

The workflow runs on push to `main`, pull request to `main`, or manual dispatch. CI installs `requirements.txt`, checks Python syntax/imports and runs `test_api.py` with a mocked model. The deploy job runs only after CI succeeds on a push to `main` or a manual dispatch from `main`. It calls `POST /api/application.deploy` with JSON `applicationId` and header `x-api-key`.

Set only these repository secrets; they are not shared automatically with other GitHub repositories:

| Secret | Value |
|---|---|
| `DOKPLOY_URL` | HTTPS base URL of Dokploy |
| `DOKPLOY_API_KEY` | Dokploy API key with deploy permission |
| `DOKPLOY_APPLICATION_ID` | ID of the existing Python Application `sign-language` |

Run `workflow_dispatch` from `main` or push a reviewed commit to `main`. A 2xx API response means Dokploy accepted the trigger; it does **not** prove the build or container startup succeeded. Inspect the Application's Deployments and Logs tabs, confirm the latest deployment finishes successfully, and check its health state. [Dokploy deployment API](https://docs.dokploy.com/docs/api/deployment) exposes records, but this workflow does not poll them because a reliable final-state contract for this installed version has not been verified.

## Private networking and Spring Boot

Do not assume the hostname `sign-language` resolves from Spring Boot. Inspect both Docker services and their networks on the VPS:

```bash
docker service ls
docker network ls
docker service inspect PYTHON_SERVICE --format '{{json .Spec.TaskTemplate.Networks}}'
docker service inspect SPRING_BOOT_SERVICE --format '{{json .Spec.TaskTemplate.Networks}}'
```

Both services must share a suitable internal Docker network on the same Docker/Swarm environment. Dokploy's default networking, isolated Compose networks, and remote servers differ; verify the actual network rather than creating an external one by assumption. If a shared network is missing, plan its creation and persistent attachment for both Applications with the backend owner. Do not alter the running backend or frontend as part of this repository change.

Determine the Python service's actual resolvable DNS name from its Docker service name/network aliases and test **inside the Spring Boot container**:

```bash
getent hosts INTERNAL_SERVICE_HOSTNAME
curl --fail --show-error http://INTERNAL_SERVICE_HOSTNAME:8000/health
curl --fail --show-error -F 'image=@hand.jpg' http://INTERNAL_SERVICE_HOSTNAME:8000/api/v1/predict
```

Use the backend's HTTP client or a diagnostic container on the same network if `curl` is absent. Configure `PYTHON_SERVICE_URL=http://INTERNAL_SERVICE_HOSTNAME:8000` in Spring Boot. This Python repository cannot confirm whether the backend already reads that variable; add support in the backend repository if needed. Set connection/read timeouts there. Authentication of users stays in Spring Boot. If untrusted containers can reach the private network, add service-to-service authentication.

## Local testing, troubleshooting and rollback

```bash
docker build -t signify-python:local .
```

For local Compose, copy `.env.example` to `.env` and set `SIGNIFY_MODEL_PATH` to an **absolute path on that machine**. Compose builds the local Dockerfile and mounts the model read-only; it does not publish a host port.

```bash
docker compose config
docker compose up --build -d
docker compose ps
docker compose logs -f signify-python
```

Check `/health` from another container on the Compose network or from within the Python container. Prediction uses multipart field `image`; it returns 200 for a confident result, 400 for invalid input, 413 over 10 MiB, and 422 for no hand/low confidence. A missing/unreadable model produces a clear startup error. `/health` confirms the process responds after model load but does not perform full inference.

For failures, inspect Dokploy build/deployment logs, model mount path/permissions, dependency installation, network membership, DNS and Gunicorn output. No public Python endpoint should be reachable. To roll back source, redeploy a known good commit through Dokploy or revert on `main` and let CI trigger a new build; restore the previous model file if it changed. Avoid assuming that rerunning a workflow for an old commit makes Dokploy clone that commit: the Application is configured to clone its current `main` branch.
