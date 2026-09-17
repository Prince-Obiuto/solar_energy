# Build context is repository root, filtered by /.dockerignore.
FROM node:24-bookworm-slim AS builder
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/src ./src
COPY frontend/public ./public
COPY frontend/index.html frontend/vite.config.js ./
ENV VITE_API_BASE_URL=/api/v1 VITE_WS_URL=""
RUN npm run build

FROM nginx:stable-alpine AS runtime
COPY deployment/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /build/dist /usr/share/nginx/html
# Skip image entrypoint scripts that try to rewrite read-only configuration.
ENTRYPOINT ["nginx"]
CMD ["-g", "daemon off;"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 CMD wget --no-check-certificate -q -O /dev/null https://127.0.0.1/healthz || exit 1
