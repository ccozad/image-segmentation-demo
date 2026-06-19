# Deploying to a single GPU host

This recipe runs the whole stack on one GPU-enabled VM with real AWS S3 and
automatic HTTPS. It is the "shippable demo" path — not a high-availability or
multi-host setup (see [Out of scope](#out-of-scope)).

The same API and worker images run in dev and prod; **only environment
changes** select MinIO vs. S3. The frontend is the one component built
differently for prod (a static nginx bundle instead of the Vite dev server).

> ⚠️ This document has **not** been executed end-to-end (it needs a GPU host,
> the gated SAM 3 checkpoint, and a public domain). Treat the exact versions and
> the cost figure as starting points to verify, not guarantees.
>
> Just want to **test the GPU worker** (not a public deploy)? See
> [`test-on-aws.md`](./test-on-aws.md) — the dev stack on a GPU instance over an
> SSH tunnel, no domain/TLS/S3 required.

## Cost — read this first

A GPU host bills by the hour whether or not anyone is using the demo.

| Instance (AWS, us-east-1) | GPU | On-demand (approx.) | Per day | Per month |
| ------------------------- | --- | ------------------- | ------- | --------- |
| `g5.xlarge`               | 1× A10G 24 GB | ~$1.01/hr  | ~$24    | ~$725     |
| `g4dn.xlarge`             | 1× T4 16 GB   | ~$0.53/hr  | ~$13    | ~$385     |

Prices change — confirm current rates before provisioning, and **stop or
terminate the instance when you're done**. A spot instance or a scheduled
stop/start cuts this substantially. (Your own RTX 3060 box costs only
electricity and is the cheapest place to run this.)

## 1. Provision the host

- A GPU VM with **≥ 16 GB VRAM** (T4/A10G class; a 12 GB card like an RTX 3060
  also works for image inference), **≥ 30 GB disk** (CUDA image + checkpoint),
  Ubuntu 24.04.
- Open inbound **80** and **443** (Caddy needs both for ACME/HTTPS).

## 2. Install Docker + the NVIDIA Container Toolkit

```sh
# Docker Engine + compose plugin
curl -fsSL https://get.docker.com | sh

# NVIDIA Container Toolkit (lets containers see the GPU)
# https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# sanity check
docker run --rm --gpus all nvidia/cuda:12.6.2-base-ubuntu24.04 nvidia-smi
```

## 3. DNS

Point two A records at the host's public IP:

- `app.example.com` → frontend
- `api.example.com` → API

## 4. Configure `.env`

```sh
git clone https://github.com/ccozad/image-segmentation-demo.git
cd image-segmentation-demo
cp .env.example .env
```

Edit `.env` for production (see the "Production overrides" block in
`.env.example`):

- **Object storage → real S3:** comment out `S3_ENDPOINT` and
  `S3_PUBLIC_ENDPOINT`, set `RAW_BUCKET` / `ANNOTATED_BUCKET` to existing S3
  buckets and `S3_REGION` to their region.
- **Credentials:** set `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`, **or**
  leave them unset and attach an **IAM instance role** with `s3:GetObject` /
  `s3:PutObject` on the buckets (boto3 picks it up automatically).
- **Hugging Face:** set `HF_TOKEN` (gated `facebook/sam3.1` — see the README).
- **Domains / CORS:** set `PUBLIC_API_URL=https://api.example.com`,
  `APP_DOMAIN=app.example.com`, `API_DOMAIN=api.example.com`, and
  `CORS_ORIGINS=["https://app.example.com"]`.

## 5. Launch

```sh
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile gpu \
  up -d --build postgres nats api web segmentation_worker caddy

# apply database migrations
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  run --rm api alembic upgrade head
```

Notes:

- MinIO is **not** listed, so it never starts — storage is real S3.
- Caddy provisions TLS certificates on first request; give it a minute.
- First worker boot downloads the checkpoint (several GB) into the `hf_cache`
  volume; `docker compose ... logs -f segmentation_worker` shows `sam3.loaded`
  when ready.

Visit `https://app.example.com`, upload an image with a prompt, and watch it go
`pending → processing → done`.

## Updating

```sh
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile gpu \
  up -d --build api web segmentation_worker
```

## Out of scope

Kubernetes / ECS / Fargate, auto-scaling, multi-host orchestration, and a
managed-Postgres (RDS) migration. The single Postgres container here is fine for
a demo; for anything real, move it to managed Postgres and back the `hf_cache`
and DB with durable storage.
