# image-segmentation-demo

An end-to-end async image segmentation pipeline. Upload an image plus a free-text
concept prompt (e.g. "cars"), and the system segments instances of that concept
and returns an annotated image. A React frontend talks to a FastAPI service that
persists raw images to object storage and dispatches work over NATS to a Python
worker running SAM 3 + OpenCV 5.

## Run locally

Requires Docker and Docker Compose.

```sh
cp .env.example .env
make up
```

This brings up the infrastructure services:

- **Postgres** — job metadata (`localhost:5432`)
- **NATS** — async message bus (`localhost:4222`, monitoring on `:8222`)
- **MinIO** — S3-compatible object storage (API `localhost:9000`, console `localhost:9001`)

On first boot a one-shot init container creates the `raw` and `annotated`
buckets. Default MinIO console login is `minioadmin` / `minioadmin`.

Make targets:

| Command      | Description                                  |
| ------------ | -------------------------------------------- |
| `make up`    | Start services and wait until healthy        |
| `make down`  | Stop services (volumes preserved)            |
| `make logs`  | Tail logs from all services                  |
| `make clean` | Stop services and delete volumes (full reset)|

## Architecture

The application services (FastAPI API, segmentation worker, React frontend) land
in later milestones — full architecture diagram coming in M2. This milestone (M0)
stands up the infrastructure layer only.

## License

[MIT](LICENSE)
