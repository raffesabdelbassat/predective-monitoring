import asyncio
import csv
import io
import os
from datetime import timedelta

from fastapi import Body, Depends, FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import func, inspect, text
from sqlalchemy.orm import Session

from ai import detect_anomalies
from alerts import check_alerts, get_alert_config
from db import AlertHistory, Base, Metric, ProcessSnapshot, SessionLocal, engine, get_db, utcnow
from failure import predict_failures
from forecast import forecast_cpu
from health import calculate_health_score
from schemas import AlertConfigIn, MetricIn, ProcessIn


app = FastAPI(title="Predictive Monitoring API", version="1.0.0")
allowed_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

Base.metadata.create_all(bind=engine)

with engine.begin() as connection:
    metric_columns = {column["name"] for column in inspect(connection).get_columns("metrics")}
    if "hostname" not in metric_columns:
        connection.execute(text(
            "ALTER TABLE metrics ADD COLUMN hostname VARCHAR(255) NOT NULL DEFAULT 'localhost'"
        ))


@app.get("/")
def read_root():
    return {"message": "Predictive Monitoring API is running", "docs": "/docs"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/health/ready")
def readiness_check(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ready", "database": "connected"}


@app.get("/status/{service_name}")
def service_status(service_name: str):
    if service_name.lower() in {"api", "backend"}:
        return {"service": service_name, "status": "healthy"}
    return {"service": service_name, "status": "unknown"}


@app.post("/metrics", status_code=201)
def receive_metrics(metrics: MetricIn, db: Session = Depends(get_db)):
    db_metric = Metric(**metrics.model_dump())
    db.add(db_metric)
    db.commit()
    db.refresh(db_metric)
    return {"status": "stored", "id": db_metric.id, "timestamp": db_metric.timestamp}


@app.get("/metrics")
def list_metrics(
    limit: int = Query(default=100, ge=1, le=1000),
    hostname: str | None = Query(default=None, min_length=1, max_length=255),
    db: Session = Depends(get_db),
):
    query = db.query(Metric)
    if hostname:
        query = query.filter(Metric.hostname == hostname)
    return query.order_by(Metric.timestamp.desc()).limit(limit).all()


@app.get("/metrics/latest")
def latest_metric(
    hostname: str | None = Query(default=None, min_length=1, max_length=255),
    db: Session = Depends(get_db),
):
    query = db.query(Metric)
    if hostname:
        query = query.filter(Metric.hostname == hostname)
    metric = query.order_by(Metric.timestamp.desc()).first()
    if metric is None:
        return {"message": "No metrics recorded yet"}
    return metric


@app.get("/devices")
def list_devices(db: Session = Depends(get_db)):
    last_seen_by_host = (
        db.query(Metric.hostname, func.max(Metric.timestamp).label("last_seen"))
        .group_by(Metric.hostname)
        .order_by(Metric.hostname.asc())
        .all()
    )
    offline_before = utcnow() - timedelta(seconds=60)
    return [
        {
            "hostname": hostname,
            "last_seen": last_seen.isoformat(),
            "status": "online" if last_seen >= offline_before else "offline",
        }
        for hostname, last_seen in last_seen_by_host
    ]


@app.get("/metrics/stats")
def metrics_stats(
    hostname: str | None = Query(default=None, min_length=1, max_length=255),
    db: Session = Depends(get_db),
):
    query = db.query(
        func.avg(Metric.cpu_percent),
        func.avg(Metric.memory_percent),
        func.avg(Metric.disk_percent),
        func.count(Metric.id),
    )
    if hostname:
        query = query.filter(Metric.hostname == hostname)
    result = query.first()
    return {
        "avg_cpu_percent": round(result[0], 2) if result[0] is not None else None,
        "avg_memory_percent": round(result[1], 2) if result[1] is not None else None,
        "avg_disk_percent": round(result[2], 2) if result[2] is not None else None,
        "sample_count": result[3],
    }


@app.get("/predictions/anomaly")
def get_anomaly_check(db: Session = Depends(get_db)):
    return detect_anomalies(db)


@app.get("/predictions/forecast")
def get_forecast(hours: int = Query(default=1, ge=1, le=168), db: Session = Depends(get_db)):
    return forecast_cpu(db, hours_ahead=hours)


@app.get("/predictions/failure")
def get_failure_prediction(db: Session = Depends(get_db)):
    return predict_failures(db)


@app.get("/alerts")
def get_alerts(db: Session = Depends(get_db)):
    return check_alerts(db)


@app.get("/alerts/history")
def alert_history(limit: int = Query(default=50, ge=1, le=500), db: Session = Depends(get_db)):
    return db.query(AlertHistory).order_by(AlertHistory.timestamp.desc()).limit(limit).all()


@app.get("/alerts/config")
def read_alert_config(db: Session = Depends(get_db)):
    config = get_alert_config(db)
    return {
        "cpu_threshold": config.cpu_threshold,
        "memory_threshold": config.memory_threshold,
        "disk_threshold": config.disk_threshold,
    }


@app.put("/alerts/config")
def update_alert_config(config_in: AlertConfigIn, db: Session = Depends(get_db)):
    config = get_alert_config(db)
    for key, value in config_in.model_dump().items():
        setattr(config, key, value)
    db.commit()
    db.refresh(config)
    return {
        "cpu_threshold": config.cpu_threshold,
        "memory_threshold": config.memory_threshold,
        "disk_threshold": config.disk_threshold,
    }


@app.get("/health/score")
def get_health_score(db: Session = Depends(get_db)):
    return calculate_health_score(db)


@app.post("/processes", status_code=201)
def receive_processes(processes: list[ProcessIn] = Body(..., max_length=100), db: Session = Depends(get_db)):
    timestamp = utcnow()
    db.add_all([
        ProcessSnapshot(timestamp=timestamp, **process.model_dump())
        for process in processes
    ])
    db.commit()
    return {"status": "stored", "count": len(processes), "timestamp": timestamp}


@app.get("/processes")
def list_processes(limit: int = Query(default=10, ge=1, le=100), db: Session = Depends(get_db)):
    latest = db.query(func.max(ProcessSnapshot.timestamp)).scalar()
    if latest is None:
        return []
    return (
        db.query(ProcessSnapshot)
        .filter(ProcessSnapshot.timestamp == latest)
        .order_by(ProcessSnapshot.cpu_percent.desc())
        .limit(limit)
        .all()
    )


@app.get("/metrics/export")
def export_metrics(db: Session = Depends(get_db)):
    rows = db.query(Metric).order_by(Metric.timestamp.asc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "timestamp", "hostname", "cpu_percent", "memory_percent", "disk_percent", "net_bytes_sent", "net_bytes_recv"])
    for row in rows:
        writer.writerow([
            row.id,
            row.timestamp.isoformat(),
            row.hostname,
            row.cpu_percent,
            row.memory_percent,
            row.disk_percent,
            row.net_bytes_sent,
            row.net_bytes_recv,
        ])
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=metrics_export.csv"},
    )


@app.websocket("/ws/metrics")
async def websocket_metrics(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            with SessionLocal() as db:
                latest = db.query(Metric).order_by(Metric.timestamp.desc()).first()
                alerts_data = check_alerts(db)
                payload = {
                    "latest": None,
                    "alert_count": alerts_data["alert_count"],
                    "alerts": alerts_data["alerts"],
                }
                if latest:
                    payload["latest"] = {
                        "id": latest.id,
                        "hostname": latest.hostname,
                        "cpu_percent": latest.cpu_percent,
                        "memory_percent": latest.memory_percent,
                        "disk_percent": latest.disk_percent,
                        "timestamp": latest.timestamp.isoformat(),
                    }
            await websocket.send_json(payload)
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        return
