# Predictive Monitoring

A small system health platform that collects machine resource readings, stores them in TimescaleDB, and presents trends, capacity estimates, and alerts in a browser dashboard.

## Components

- **Collector** — samples CPU, memory, disk, network, and the five busiest processes every 10 seconds.
- **FastAPI backend** — validates and stores readings, computes resource forecasts and anomaly checks, records alert history, and exposes a WebSocket stream.
- **TimescaleDB** — PostgreSQL-compatible storage for metrics, process snapshots, thresholds, and alert history.
- **React dashboard** — shows current health, resource charts, active alerts, forecasts, process snapshots, alert history, and editable thresholds.

## Run the platform

Install Docker Desktop, then run from the repository root:

```bash
docker compose up --build
```

Open:

- Dashboard: <http://localhost:3000>
- API: <http://localhost:8000>
- API documentation: <http://localhost:8000/docs>
- Readiness check: <http://localhost:8000/health/ready>
- PostgreSQL: `localhost:5433`

The Compose defaults are intended for local development. Set `POSTGRES_PASSWORD` to a strong value before using a network accessible deployment. You can also set `API_PORT`, `FRONTEND_PORT`, `POSTGRES_PORT`, `CORS_ORIGINS`, and `VITE_API_URL` in the environment before starting Compose.

## Start the collector

The collector runs on the machine being monitored. With the platform running, install its dependencies and start it:

```bash
python -m pip install -r agent/requirements.txt
python agent/collector.py
```

Set `MONITORING_API_URL` if the API is not at `http://127.0.0.1:8000`. Set `COLLECTION_INTERVAL_SECONDS` to change the sampling interval; values below two seconds are raised to two seconds.

## API overview

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/metrics` | Store a resource reading |
| `GET` | `/metrics`, `/metrics/latest`, `/metrics/stats` | Read metric history and summaries |
| `GET` | `/predictions/anomaly` | Check the latest reading for unusual behavior |
| `GET` | `/predictions/forecast?hours=1` | Estimate CPU usage 1–168 hours ahead |
| `GET` | `/predictions/failure` | Estimate time to resource capacity from recent trends |
| `GET` | `/alerts` | Return active alert conditions |
| `GET`, `PUT` | `/alerts/config` | Read or update CPU, memory, and disk thresholds |
| `GET` | `/alerts/history` | Read recorded alert events |
| `POST`, `GET` | `/processes` | Store and read the latest process snapshot |
| `GET` | `/metrics/export` | Download metric history as CSV |
| WebSocket | `/ws/metrics` | Receive current readings and alerts every five seconds |

Forecast and anomaly endpoints need at least ten metric samples. Capacity estimates use recent samples and report a trend confidence; treat them as operational guidance rather than a guaranteed failure time.

## Run checks

Frontend build and tests:

```bash
cd frontend
npm ci
npm test
npm run build
```

Backend tests (Python 3.12 recommended):

```bash
python -m pip install -r backend/requirements-dev.txt
python -m pytest backend/tests
```

The tests use an in-memory SQLite database and do not require Docker or a running database.
