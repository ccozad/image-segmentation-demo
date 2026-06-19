# ── dev: Vite dev server (default target used by docker-compose) ──────────────
FROM node:22-alpine AS dev
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev"]

# ── build: produce the static bundle ─────────────────────────────────────────
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
# VITE_API_URL is baked at build time for prod; override via build arg (M5).
ARG VITE_API_URL
RUN npm run build

# ── prod: nginx (unprivileged, non-root) serving the static bundle ───────────
# nginxinc/nginx-unprivileged runs as UID 101 and listens on 8080.
FROM nginxinc/nginx-unprivileged:1.27-alpine AS prod
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=5 \
    CMD wget -q -O- http://localhost:8080/ >/dev/null 2>&1 || exit 1
