# ---- build ----
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Empty => the browser calls same-origin /api, which nginx proxies to the API container.
ARG VITE_API_URL=""
ARG VITE_TILE_URL=""
ENV VITE_API_URL=$VITE_API_URL VITE_TILE_URL=$VITE_TILE_URL
RUN npm run build

# ---- serve (static files + /api reverse proxy; no Vite dev server) ----
FROM nginxinc/nginx-unprivileged:1.27-alpine
ENV API_UPSTREAM=http://api:8000 MAX_UPLOAD_MB=550 TILE_CSP_SOURCES=https://tile.openstreetmap.org
COPY deploy/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --retries=5 CMD wget -qO- http://127.0.0.1:8080/healthz >/dev/null || exit 1
