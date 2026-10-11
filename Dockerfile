
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    libpq-dev \
    gdal-bin \
    proj-bin \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

ENV GDAL_VERSION=3.6.2
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

WORKDIR /build

COPY pyproject.toml ./

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -e ".[dev]" || \
    pip install --no-cache-dir \
        "fastapi[standard]==0.115.0" \
        "uvicorn[standard]==0.32.0" \
        "pydantic==2.10.0" \
        "pydantic-settings==2.6.0" \
        "sqlalchemy==2.0.36" \
        "alembic==1.14.0" \
        "asyncpg==0.30.0" \
        "psycopg2-binary==2.9.10" \
        "geoalchemy2==0.15.2" \
        "geopandas==1.0.1" \
        "shapely==2.0.6" \
        "pyproj==3.7.0" \
        "fiona==1.10.1" \
        "argon2-cffi==23.1.0" \
        "pyjwt==2.10.0" \
        "structlog==24.4.0" \
        "reportlab==4.2.5" \
        "python-multipart==0.0.17" \
        "python-magic==0.4.27" \
        "arq==0.26.1" \
        "redis==5.2.0" \
        "slowapi==0.1.9" \
        "jinja2==3.1.4" \
        "httpx==0.28.0" \
        "aiofiles==24.1.0"


FROM python:3.12-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    libpq5 \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1001 geoapi && \
    useradd --uid 1001 --gid geoapi --shell /bin/bash --create-home geoapi

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY --chown=geoapi:geoapi app/ ./app/
COPY --chown=geoapi:geoapi alembic/ ./alembic/
COPY --chown=geoapi:geoapi alembic.ini ./
COPY --chown=geoapi:geoapi scripts/ ./scripts/

RUN mkdir -p /app/uploads && chown geoapi:geoapi /app/uploads

USER geoapi

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--log-level", "info", \
     "--no-access-log"]
