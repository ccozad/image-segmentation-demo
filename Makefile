.PHONY: up up-gpu down logs clean migrate

# Bring up the stack WITHOUT the GPU worker (works on any machine). Brings up
# infra, creates buckets, starts the API + web frontend, and migrates.
# Jobs stay "pending" until a GPU worker is running (see `up-gpu`).
up:
	docker compose up -d --wait postgres nats minio
	docker compose run --rm minio-init
	docker compose up -d --wait api web
	$(MAKE) migrate

# Full stack including the GPU segmentation worker. Requires an NVIDIA GPU host.
up-gpu:
	docker compose --profile gpu up -d --wait postgres nats minio
	docker compose run --rm minio-init
	docker compose --profile gpu up -d --wait api web segmentation_worker
	$(MAKE) migrate

# Apply database migrations (runs Alembic inside the api image).
migrate:
	docker compose run --rm api alembic upgrade head

# Stop and remove containers (volumes preserved).
down:
	docker compose down

# Tail logs from all services.
logs:
	docker compose logs -f

# Stop everything and delete named volumes (full reset).
clean:
	docker compose down -v
