# 🌍 Geospatial Measurement API

[![CI](https://github.com/your-org/geospatial-api/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/geospatial-api/actions)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Production-grade REST API** for geospatial file measurement. Upload GeoJSON, KML, or zipped Shapefiles and get accurate area, perimeter, centroid, bounding box, feature counts, geometry statistics, unit conversion, paginated history, an interactive Leaflet preview, and a downloadable PDF report.

---

## 📐 Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                     FastAPI Application                  │
│                                                          │
│  ┌─────────────┐   ┌──────────────┐  ┌──────────────┐  │
│  │  api/v1/    │   │    auth/     │  │    core/     │  │
│  │  (routers)  │──▶│ (JWT, deps)  │  │ (config,log) │  │
│  └──────┬──────┘   └──────────────┘  └──────────────┘  │
│         │                                                │
│  ┌──────▼──────┐   ┌──────────────┐  ┌──────────────┐  │
│  │  services/  │──▶│ repositories/│  │   database/  │  │
│  │ (business)  │   │ (data access)│  │ (SQLAlchemy) │  │
│  └──────┬──────┘   └──────────────┘  └──────────────┘  │
│         │                                                │
│  ┌──────▼──────────────────────────────────────────┐    │
│  │              Core Services                       │    │
│  │  parsers.py    measurement_service.py            │    │
│  │  unit_converter.py  storage_service.py           │    │
│  │  report_service.py  geo_file_service.py          │    │
│  └──────────────────────────────────────────────────┘    │
└────────────────────┬────────────────────────────────────┘
                     │ async queue (ARQ)
          ┌──────────▼──────────┐
          │   Background Worker  │
          │   (arq_worker.py)   │
          └──────────┬──────────┘
                     │
     ┌───────────────┼───────────────┐
     │               │               │
 ┌───▼───┐    ┌──────▼──────┐  ┌───▼───┐
 │PostGIS│    │    Redis     │  │ Files │
 │  DB   │    │  (job queue) │  │  FS   │
 └───────┘    └─────────────┘  └───────┘
```

---

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- (Optional for local dev) Python 3.12, GDAL, PROJ

### 1. Clone and configure

```bash
git clone https://github.com/your-org/geospatial-api
cd geospatial-api
cp .env.example .env
# Edit .env and set a strong SECRET_KEY and POSTGRES_PASSWORD
openssl rand -hex 32   # → use this as SECRET_KEY
```

### 2. Start everything with Docker

```bash
docker compose up --build
```

Services:
| Service | URL |
|---------|-----|
| API (Swagger) | http://localhost:8000/api/v1/docs |
| API (ReDoc) | http://localhost:8000/api/v1/redoc |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

### 3. Run migrations (first time only)

```bash
docker compose run --rm migrate
```

---

## 🖥️ Local Development (without Docker)

```bash
# Install system deps (Ubuntu/Debian)
sudo apt-get install libgdal-dev libgeos-dev libproj-dev gdal-bin libmagic1

# Create virtualenv and install
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Configure .env for local Postgres
cp .env.example .env
# Set POSTGRES_HOST=localhost etc.

# Apply migrations
alembic upgrade head

# Generate test fixtures
python scripts/create_shapefile_fixture.py

# Start the API
uvicorn app.main:app --reload --port 8000
```

---

## 📡 API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/auth/register` | Register new user |
| `POST` | `/api/v1/auth/login` | Login, get JWT pair |
| `POST` | `/api/v1/auth/refresh` | Refresh access token |
| `GET`  | `/api/v1/auth/me` | Current user profile |

### Files & Measurements

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST`   | `/api/v1/files/upload` | Upload GeoJSON/KML/Shapefile ZIP |
| `GET`    | `/api/v1/files` | Paginated file history |
| `GET`    | `/api/v1/files/{id}/measurements` | Measurement results (with `?unit=ha`) |
| `GET`    | `/api/v1/files/{id}/features` | Per-feature breakdown |
| `GET`    | `/api/v1/files/{id}/geojson` | GeoJSON for map rendering |
| `GET`    | `/api/v1/files/{id}/report.pdf` | Download PDF report |
| `DELETE` | `/api/v1/files/{id}` | Delete file + all data |
| `GET`    | `/api/v1/map/{id}` | Leaflet map preview |
| `GET`    | `/api/v1/jobs/{id}` | Background job status |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Liveness probe |
| `GET` | `/ready` | Readiness probe (DB + Redis) |

---

## 📋 Example cURL Requests

```bash
# Register
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","username":"johndoe","password":"SecurePass123!"}'

# Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"SecurePass123!"}' | jq -r .access_token)

# Upload a GeoJSON file
curl -X POST http://localhost:8000/api/v1/files/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@tests/fixtures/geojson/simple.geojson"

# Get measurements (in hectares)
curl http://localhost:8000/api/v1/files/{FILE_ID}/measurements?unit=ha \
  -H "Authorization: Bearer $TOKEN"

# Download PDF report
curl -O report.pdf \
  http://localhost:8000/api/v1/files/{FILE_ID}/report.pdf \
  -H "Authorization: Bearer $TOKEN"

# Open Leaflet map
open http://localhost:8000/api/v1/map/{FILE_ID}
# (requires Bearer token in a real browser flow)
```

---

## 🧮 Design Decisions

### Why Geodesic Area?

Computing area from raw latitude/longitude coordinates treats degrees as if they were uniform Euclidean units — a degree of longitude is ~111 km at the equator but only ~55 km at 60°N. This introduces errors of **5–15% at mid-latitudes** and can exceed 50% near the poles.

**Our approach**: We use [`pyproj.Geod.geometry_area_perimeter()`](https://pyproj4.github.io/pyproj/stable/api/geod.html) which integrates the polygon boundary along true geodesic arcs on the WGS84 ellipsoid (a=6 378 137 m, f=1/298.257 223 563). This matches:
- PostGIS `ST_Area(geography)` (ellipsoidal mode)
- QGIS area tool with "Ellipsoidal" selected
- PROJ's native geodesic calculations

**Verification**: A 1 000 × 1 000 m UTM square (EPSG:32632) reprojected to WGS84 and measured geodesically gives **100.00 ha ± 0.01%** — confirmed by our test suite.

### CRS Strategy

| Input format | Default CRS | Notes |
|---|---|---|
| GeoJSON | EPSG:4326 (RFC 7946 §4) | Any embedded CRS member is honoured with a warning |
| KML | EPSG:4326 (OGC spec) | Always WGS84 |
| Shapefile | From `.prj` file | Missing `.prj` → 422 error |
| Projected CRS | As declared | Planimetric computation in source CRS |

### Centroid Computation

Raw lat/lon centroids are incorrect for non-convex or large polygons. We:
1. Find the approximate centroid from the bounding box midpoint
2. Determine the local UTM zone from that coordinate
3. Project to UTM, compute the centroid in Cartesian space
4. Back-project to WGS84

### Async Processing

Files above `ASYNC_PROCESSING_THRESHOLD_MB` (default: 5 MB) are processed by an ARQ background worker. The upload endpoint returns `202 Accepted` with a `job_id`. Poll `GET /jobs/{job_id}` for status. Sync processing returns the result inline.

### Security

- Passwords hashed with **argon2** (winner of Password Hashing Competition)
- Stale hashes transparently rehashed on login
- JWTs have separate access (30 min) and refresh (7 day) tokens with explicit type validation
- Files stored under **UUID names** — original filenames are never used on disk
- **Zip-slip** protection: entries with `..` path components are rejected
- **Zip-bomb** protection: total uncompressed size capped at 500 MB; max 100 entries

---

## 📊 Known Limitations

1. **Antimeridian-crossing polygons**: GeoPandas/Shapely can produce incorrect results for polygons crossing the ±180° meridian. Use PostGIS `ST_Split` / `ST_Intersection` to pre-split such geometries.
2. **Very large files (>50 MB)**: Supported via async processing but memory usage scales with feature count. Consider streaming parsing for truly massive files.
3. **3D geometries**: Z-coordinates are currently ignored for area/perimeter calculations (projected to 2D).
4. **KML network links**: `<NetworkLink>` and `<GroundOverlay>` elements are not supported.

---

## 🧪 Running Tests

```bash
# Unit tests only (no external services needed)
pytest tests/unit/ -v

# All tests (requires PostgreSQL + Redis)
pytest tests/ --cov=app --cov-report=html -v

# Specific test
pytest tests/unit/test_measurement.py::TestGeodesicArea::test_1km_square_is_approx_100_ha -v
```

---

## 🌍 Environment Variables

See [.env.example](.env.example) for the full reference. Key variables:

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | ✅ | — | JWT signing key (min 32 chars) |
| `POSTGRES_PASSWORD` | ✅ | — | Database password |
| `POSTGRES_HOST` | | `db` | DB hostname |
| `REDIS_URL` | | `redis://redis:6379/0` | Redis connection URL |
| `MAX_FILE_SIZE_MB` | | `50` | Upload size limit |
| `ASYNC_PROCESSING_THRESHOLD_MB` | | `5` | Files larger than this → async |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | | `30` | JWT access token lifetime |

---

## 🏗️ Project Structure

```
app/
├── api/v1/          # FastAPI routers (thin layer, no business logic)
│   ├── auth.py
│   ├── files.py
│   ├── jobs.py
│   ├── health.py
│   └── map.py
├── auth/            # JWT dependency injection
│   └── dependencies.py
├── core/            # Config, logging, exceptions, middleware, security
├── database/        # SQLAlchemy engine, session, base model
├── models/          # ORM models (User, GeoFile, GeoFeature)
├── schemas/         # Pydantic request/response models
├── services/        # Business logic (measurement, parsers, units, report, storage)
├── repositories/    # Data-access layer (no FastAPI deps)
├── workers/         # ARQ background workers
├── templates/       # Jinja2 templates (Leaflet map)
└── main.py          # Application factory
tests/
├── unit/            # Pure unit tests (no DB/network)
├── integration/     # HTTP integration tests with httpx
├── fixtures/        # Sample GeoJSON, KML, Shapefile ZIP
└── conftest.py      # Shared pytest fixtures
```

---

## ✅ Requirement → Implementation Mapping

| Requirement | File(s) |
|---|---|
| Geodesic area (no degrees) | `services/measurement_service.py` → `_geodesic_area_perimeter()` |
| CRS detection + geodesic/planimetric | `services/measurement_service.py` → `_is_geographic()` |
| Shapefile .prj parsing | `services/parsers.py` → `ShapefileParser._resolve_crs()` |
| Missing CRS → 422 | `core/exceptions.py` → `MissingCRSError` |
| Invalid geometry repair | `services/measurement_service.py` → `_validate_and_repair()` |
| Unit conversion (exact constants) | `services/unit_converter.py` |
| GeoJSON parser | `services/parsers.py` → `GeoJSONParser` |
| KML parser | `services/parsers.py` → `KMLParser` |
| Shapefile parser | `services/parsers.py` → `ShapefileParser` |
| Parser factory (OCP) | `services/parsers.py` → `ParserFactory` |
| Auth (JWT + argon2) | `core/security.py`, `auth/dependencies.py`, `services/auth_service.py` |
| Upload validation (magic bytes) | `services/storage_service.py` |
| Zip-slip protection | `services/parsers.py` → `_check_zip_safety()` |
| UUID filenames | `services/storage_service.py` |
| PostGIS geometry storage | `models/geo_file.py` + migration |
| JSONB result storage | `models/geo_file.py` → `measurement_result` |
| GiST index | `models/geo_file.py` + `alembic/versions/0001_initial.py` |
| Async processing (ARQ) | `workers/arq_worker.py` |
| Leaflet map | `templates/map.html`, `api/v1/map.py` |
| PDF report | `services/report_service.py` |
| Structured logging | `core/logging.py` (structlog) |
| Request ID middleware | `core/middleware.py` |
| Error envelope | `core/exceptions.py` |
| Rate limiting | `main.py` (slowapi) |
| Security headers | `core/middleware.py` → `SecurityHeadersMiddleware` |
| /health + /ready | `api/v1/health.py` |
| Unit tests (measurement) | `tests/unit/test_measurement.py` |
| Unit tests (converter) | `tests/unit/test_unit_converter.py` |
| Unit tests (parsers) | `tests/unit/test_parsers.py` |
| Integration tests (auth) | `tests/integration/test_auth.py` |
| Docker + docker-compose | `Dockerfile`, `docker-compose.yml` |
| GitHub Actions CI | `.github/workflows/ci.yml` |
| Alembic migrations | `alembic/versions/0001_initial.py` |
