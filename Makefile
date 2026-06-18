.PHONY: up down logs clean

# Bring up the long-running infra services and wait until healthy, then run the
# one-shot bucket init in the foreground (its exit code propagates, and --wait
# would otherwise treat the one-shot's clean exit as a failure).
up:
	docker compose up -d --wait postgres nats minio
	docker compose run --rm minio-init

# Stop and remove containers (volumes preserved).
down:
	docker compose down

# Tail logs from all services.
logs:
	docker compose logs -f

# Stop everything and delete named volumes (full reset).
clean:
	docker compose down -v
