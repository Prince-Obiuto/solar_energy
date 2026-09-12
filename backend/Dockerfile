# Build from the repository root: docker build -f backend/Dockerfile .
FROM python:3.12-slim-trixie AS dependencies
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY backend/requirements.txt .
RUN python -m venv /opt/venv && /opt/venv/bin/pip install -r requirements.txt

FROM python:3.12-slim-trixie AS runtime
ENV PATH="/opt/venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=Africa/Lagos
# Debian trixie's PostgreSQL 17 client matches the deployment database for pg_dump.
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates tzdata postgresql-client-17 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 solar && useradd --uid 10001 --gid 10001 --no-create-home solar
COPY --from=dependencies /opt/venv /opt/venv
WORKDIR /opt/solar/backend
COPY backend/apps ./apps
COPY backend/migrations ./migrations
COPY backend/alembic.ini ./alembic.ini
COPY backend/docker/entrypoint.py /opt/solar/entrypoint.py
# Only the proven library; never the standalone reader, credentials, or captures.
# Its existing import fallback resolves /opt/solar/energy without application changes.
COPY energy/siseli/__init__.py energy/siseli/api.py energy/siseli/const.py /opt/solar/energy/siseli/
RUN PYTHONPATH=/opt/solar/energy python -c "from siseli.api import SolarOfThingsAPI; assert callable(SolarOfThingsAPI)"
USER 10001:10001
ENTRYPOINT ["python", "/opt/solar/entrypoint.py"]
CMD ["python", "-m", "uvicorn", "apps.main:app", "--host", "127.0.0.1", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1", "--no-access-log"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).close()"]
