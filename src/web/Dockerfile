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

# ── prod: nginx serving the static bundle ────────────────────────────────────
FROM nginx:alpine AS prod
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
