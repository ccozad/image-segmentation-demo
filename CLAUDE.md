# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state

The repository is still at the scaffold stage. As of this writing it contains only `README.md` (title) and `.gitattributes` (LF normalization) — **no code from any milestone has landed yet.** The architecture below is the *target*, derived from GitHub issues #1–#6 (milestone "Image Segmentation Demo v1"). Treat those issues as the source of truth; check them with `gh issue view <n>` before starting work, and update this file as milestones land.

## What this becomes

An end-to-end **async image segmentation pipeline**. A user uploads an image plus a free-text concept prompt (e.g. "cars"); the system segments instances of that concept and returns an annotated image. The async loop is deliberately decoupled to mirror a real production shape:

```
React SPA ──HTTP──> FastAPI ──> Postgres (Job rows)
                       │              ▲
                  raw bytes        status/result updates
                       ▼              │
                    MinIO/S3   <─ NATS subjects ─> Python worker (SAM 3 + OpenCV 5, GPU)
```

- **API never does the ML.** `POST /images` persists the raw image to object storage, writes a `pending` `Job` row, and publishes `segment.request` on NATS.
- **Worker never writes the DB directly.** It communicates *only* over NATS (`segment.status`, `segment.result`). The API runs a subscriber task that translates those messages into DB updates. This keeps the worker swappable/replicable.
- **Job state machine:** `pending → processing → done | failed`.
- **Storage is env-switched:** MinIO in dev, real AWS S3 in prod, same code path (selected by whether `S3_ENDPOINT` is set). Two buckets: `raw` and `annotated`.

## Milestone sequence

Build strictly in order — each milestone assumes the previous one is working.

- **M0 (#1) — infra only.** `docker-compose.yml` with `postgres`, `nats` (HTTP monitoring for healthcheck), `minio` + a `minio-init` one-shot that creates the `raw`/`annotated` buckets via `mc`. Plus `.env.example`, `Makefile` (`up`/`down`/`logs`/`clean`), `LICENSE` (MIT), `.gitignore`. No app services yet. Acceptance: `cp .env.example .env && make up` → all three services `healthy`.
- **M1 (#2) — API + storage + DB.** FastAPI in `src/api/` (async SQLAlchemy + asyncpg, Alembic, boto3, structlog). `Job` model, `POST /images` (multipart file + prompt), paginated `GET /images`, `GET /images/{id}`, `GET /healthz`. Presigned URLs (15-min TTL default). Jobs stay `pending` forever here — that's expected. `make migrate` runs Alembic. pytest route tests.
- **M2 (#3) — worker stub + NATS loop.** `src/segmentation_worker/` subscribes to `segment.request`, does **fake** processing (Pillow draws a labeled rectangle, sleeps 1–2s), uploads to `annotated`, publishes `segment.result`. API gains the startup subscriber task. Must be idempotent under NATS at-least-once redelivery (check annotated-object existence before re-uploading).
- **M3 (#4) — real SAM 3 + OpenCV 5.** Replace the fake with real inference. Worker base image switches to `nvidia/cuda:12.6.x-cudnn-runtime` (PyTorch 2.10 CUDA wheels, OpenCV 5, SAM 3 pinned from `facebookresearch/sam3`). **GPU host required; CPU unsupported.** HF checkpoint (`facebook/sam3.1`) is gated — needs `HF_TOKEN`; cache it in a named volume. Zero masks → `done` with `mask_count=0` and original image; inference error → `failed`. Model must be preloaded once, not per-request.
- **M4 (#5) — React frontend.** `src/web/` Vite + React 18 + TS SPA. Three surfaces: `UploadForm` (optimistic pending row), `HistoryList`, `ImageDetailView` (raw vs annotated side by side). Polls `GET /images` every ~2s (no WebSocket). Typed `apiClient.ts`, base URL from `VITE_API_URL`. Dockerfile has dev mode (Node 22) and prod mode (multi-stage → `nginx:alpine`).
- **M5 (#6) — deployment shape.** *Optional polish.* Production Dockerfiles (non-root, pinned digests, `HEALTHCHECK`), the MinIO↔S3 env swap (`S3_ENDPOINT` set = MinIO path-style, unset = AWS virtual-hosted), and a single-GPU-host deploy recipe in `docs/deploy.md` with honest GPU cost notes.

## Conventions that span milestones

- **NATS subjects:** `segment.request` (API→worker), `segment.status` + `segment.result` (worker→API). Don't let the worker touch Postgres.
- **Object keys:** raw at `s3://${RAW_BUCKET}/${id}.{ext}`, annotated at `s3://${ANNOTATED_BUCKET}/{job_id}.png` (PNG for transparency).
- **`Job` columns:** `id (uuid)`, `raw_key`, `prompt`, `annotated_key?`, `status`, `mask_count?`, `processing_ms?`, `uploaded_at`, `completed_at?`.
- **Everything runs via Docker Compose.** Each new service (`api`, `segmentation_worker`, `web`) is added to `docker-compose.yml` with `depends_on: condition: service_healthy` on its infra deps. The `Makefile` is the entry point (`make up`, `make migrate`, etc.) — add commands there as services arrive.
- Python 3.12 throughout; API/worker images on slim bases except the worker from M3 onward (CUDA base).

## Out of scope for v1

Auth / per-user history, WebSocket realtime, clickable mask interactivity, history search/filter, batch upload, and k8s/ECS/auto-scaling/RDS recipes.
