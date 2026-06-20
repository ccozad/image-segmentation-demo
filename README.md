# image-segmentation-demo

An end-to-end async image segmentation pipeline. Upload an image plus a free-text
concept prompt (e.g. "cars"), and the system segments instances of that concept
and returns an annotated image. A React frontend talks to a FastAPI service that
persists raw images to object storage and dispatches work over NATS to a Python
worker running SAM 3 + OpenCV.

## Run locally

Requires Docker and Docker Compose.

```sh
cp .env.example .env
make up
```

`make up` brings up the stack **without** the GPU worker — it works on any
machine — and opens the frontend at **<http://localhost:5173>**:

- **Web** — React frontend (`localhost:5173`)
- **API** — FastAPI (`localhost:8000`)
- **Postgres** — job metadata (`localhost:5432`)
- **NATS** — async message bus (`localhost:4222`, monitoring on `:8222`)
- **MinIO** — S3-compatible object storage (API `localhost:9000`, console `localhost:9001`)

On first boot a one-shot init container creates the `raw` and `annotated`
buckets (MinIO console login `minioadmin` / `minioadmin`), and `make up`
applies database migrations automatically.

Without the GPU worker, uploads succeed and appear in the history as **pending**
(nothing processes them). To get real segmentation, run the full stack with
`make up-gpu` on a GPU host (see below).

> **macOS note:** `localhost` resolves to IPv6 first. If you have another dev
> server already bound to `[::1]:5173`, it will shadow this one — use
> <http://127.0.0.1:5173> to be sure you're hitting the container.

Make targets:

| Command        | Description                                            |
| -------------- | ----------------------------------------------------- |
| `make up`      | Start the stack **without** the GPU worker, + migrate |
| `make up-gpu`  | Start the full stack **including** the GPU worker     |
| `make migrate` | Apply database migrations (Alembic)                   |
| `make down`    | Stop services (volumes preserved)                     |
| `make logs`    | Tail logs from all services                           |
| `make clean`   | Stop services and delete volumes (full reset)         |

The frontend can also be developed directly on the host:
`cd src/web && npm install && npm run dev`.

## Running the segmentation worker (GPU required)

From milestone M3 on, the worker runs the real **SAM 3** model and **requires an
NVIDIA GPU host** — CPU is not supported. The `segmentation_worker` service will
not start on a machine without a GPU. (The infra + API services run fine without
one; you just won't get annotations.)

### 1. Hugging Face access + token

The `facebook/sam3.1` checkpoint is gated:

1. Request access at <https://huggingface.co/facebook/sam3.1> (approval can take
   a day or two).
2. Create a **READ** token at <https://huggingface.co/settings/tokens>.
3. Put it in your `.env`:

   ```sh
   HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

The worker fails fast with a clear message if `HF_TOKEN` is missing. The
checkpoint (several GB) downloads on first boot and is cached in the `hf_cache`
Docker volume, so later restarts skip the download.

### 2. GPU runtime

- **Linux:** install the
  [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
  so Docker can pass the GPU into containers.
- **Windows:** install a recent NVIDIA driver on Windows, enable
  **Docker Desktop → Settings → Resources → WSL Integration**, and run all
  commands **from inside a WSL2 (Ubuntu) shell** — not PowerShell. Inside WSL2,
  `make`/`docker compose` work exactly as on Linux, and the GPU is available to
  containers via the Windows driver (no separate toolkit install needed). If you
  don't have `make` in WSL2: `sudo apt install make`. (The raw equivalents also
  work, e.g. `docker compose up -d --wait postgres nats minio`.)
- **No local GPU?** See [docs/test-on-aws.md](docs/test-on-aws.md) to run on a
  rented GPU instance.

A 12 GB GPU is sufficient for SAM 3 *image* inference. Non-Compose users can pass
`--gpus all` to `docker run` instead of the Compose `deploy.resources` block.

### 3. Run

```sh
cp .env.example .env      # then edit HF_TOKEN
make up-gpu               # full stack incl. worker (large first build + checkpoint download)
```

Open <http://localhost:5173>, upload an image with a concept prompt, and the
worker highlights matching instances. A prompt with no matches returns the
original image with `mask_count = 0`.

## Architecture

```
React SPA ──HTTP──> FastAPI ──> Postgres (Job rows)
                       │              ▲
                  raw bytes        status/result updates
                       ▼              │
                    MinIO/S3   <─ NATS ─> segmentation worker (SAM 3 + OpenCV, GPU)
```

The API persists the upload and publishes a request on NATS; the worker segments
and reports status/results back over NATS; the API applies them to the job row.
The worker never touches the database directly. Storage is env-switched: MinIO in
dev, real AWS S3 in prod — the same API/worker images run in both; only env
changes.

## Deployment

To run the full stack on a single GPU host with real S3 and automatic HTTPS, see
**[docs/deploy.md](docs/deploy.md)**. It uses `docker-compose.prod.yml`
(production images — non-root, healthchecked — plus a Caddy TLS reverse proxy).

Just want to **test the GPU worker** without a local GPU? See
**[docs/test-on-aws.md](docs/test-on-aws.md)** — run the dev stack on a GPU EC2
instance and reach it over an SSH tunnel (no domain, TLS, or real S3 needed).

## License

[MIT](LICENSE)
