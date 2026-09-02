# RAIL-OPT Backend

FastAPI backend for AI-powered railway maintenance block optimization.

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Setup PostgreSQL Database

```bash
# Using Docker (recommended for demo)
docker run --name railopt-postgres \
  -e POSTGRES_USER=railopt \
  -e POSTGRES_PASSWORD=railopt_dev \
  -e POSTGRES_DB=railopt \
  -p 5432:5432 \
  -d postgres:15

# Or install PostgreSQL locally and create database
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env if needed (default settings work with Docker setup)
```

### 4. Run the Server

```bash
python run.py
```

Server starts at: http://localhost:8000

API Docs: http://localhost:8000/docs

### 5. Generate Synthetic Data

```bash
curl -X POST http://localhost:8000/api/v1/data/generate \
  -H "Content-Type: application/json" \
  -d '{"seed": 42, "weeks": 5}'
```

This generates:
- 6 corridors with varied traffic classes
- ~200 maintenance requests
- 15-20 planted bundle opportunities
- Realistic train paths and block windows

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI application
│   ├── core/
│   │   ├── config.py        # Settings
│   │   └── database.py      # DB connection
│   ├── models/              # SQLAlchemy models
│   ├── api/routers/         # API endpoints
│   └── engines/             # Optimization engines (Phase 1+)
├── synth/
│   └── generator.py         # Synthetic data generator
└── run.py                   # Dev server launcher
```

## API Endpoints (Phase 0)

- `GET /` - Health check
- `GET /health` - Detailed health status
- `POST /api/v1/data/generate` - Generate synthetic data
- `GET /api/v1/data/stats` - Get data statistics

More endpoints added in Phase 1+.

## Database Schema

Based on PRD §9 canonical data model:
- `corridor`, `station`, `track_section` - Infrastructure
- `asset`, `maintenance_request` - Work to be done
- `train`, `train_path` - Traffic constraints
- `block_window` - Available time slots
- `plan`, `planned_block` - Optimization output

## Development

Auto-reload enabled in dev mode. Edit code and server restarts automatically.

View logs for debugging. Database recreated on each startup (dev mode).
