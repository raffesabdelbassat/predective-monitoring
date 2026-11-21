import asyncio
import csv
import io
import os
import secrets

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import func, inspect, text
from sqlalchemy.orm import Session

from ai import detect_anomalies
from alerts import check_alerts, get_alert_config
from db import (
    AlertHistory,
    Base,
    METRIC_STALE_AFTER,
    Metric,
    ProcessSnapshot,
    SessionLocal,
    engine,
    get_db,
    utcnow,
)
from failure import predict_failures
from forecast import forecast_cpu
from health import calculate_health_score
from schemas import AlertConfigIn, MetricIn, ProcessIn


app = FastAPI(title="Predictive Monitoring API", version="1.0.0")
AGENT_API_KEY = os.getenv("AGENT_API_KEY", "").strip()
allowed_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Agent-Key"],
)

Base.metadata.create_all(bind=engine)

with engine.begin() as connection:
    metric_columns = {column["name"] for column in inspect(connection).get_columns("metrics")}
    if "hostname" not in metric_columns:
        connection.execute(text(
            "ALTER TABLE metrics ADD COLUMN hostname VARCHAR(255) NOT NULL DEFAULT 'localhost'"
        ))
    process_columns = {column["name"] for column in inspect(connection).get_columns("process_snapshots")}
    if "hostname" not in process_columns:
        connection.execute(text(
            "ALTER TABLE process_snapshots ADD COLUMN hostname VARCHAR(255) NOT NULL DEFAULT 'localhost'"
        ))
    alert_columns = {column["name"] for column in inspect(connection).get_columns("alert_history")}
    if "hostname" not in alert_columns:
        connection.execute(text("ALTER TABLE alert_history ADD COLUMN hostname VARCHAR(255)"))


def metric_hostnames(db: Session) -> list[str]:
    return [
        hostname
        for (hostname,) in db.query(Metric.hostname).distinct().order_by(Metric.hostname).all()
        if hostname
    ]


def verify_agent_key(x_agent_key: str | None = Header(default=None)):
    if AGENT_API_KEY and not secrets.compare_digest(x_agent_key or "", AGENT_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing agent API key")


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


@app.post("/metrics", status_code=201, dependencies=[Depends(verify_agent_key)])
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
    ranked_metrics = db.query(
        Metric.id.label("id"),
        func.row_number().over(
            partition_by=Metric.hostname,
            order_by=(Metric.timestamp.desc(), Metric.id.desc()),
        ).label("position"),
    ).subquery()
    latest_ids = db.query(ranked_metrics.c.id).filter(ranked_metrics.c.position == 1).subquery()
    latest_metrics = db.query(Metric).join(latest_ids, Metric.id == latest_ids.c.id).all()
    offline_before = utcnow() - METRIC_STALE_AFTER
    return [
        {
            "hostname": metric.hostname,
            "last_seen": metric.timestamp.isoformat(),
            "status": "online" if metric.timestamp >= offline_before else "offline",
            "cpu_percent": metric.cpu_percent,
            "memory_percent": metric.memory_percent,
            "disk_percent": metric.disk_percent,
        }
        for metric in sorted(latest_metrics, key=lambda item: item.hostname.lower())
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
def get_anomaly_check(
    hostname: str | None = Query(default=None, min_length=1, max_length=255),
    db: Session = Depends(get_db),
):
    if hostname:
        return detect_anomalies(db, hostname=hostname)

    results = [(device, detect_anomalies(db, hostname=device)) for device in metric_hostnames(db)]
    ready = [(device, result) for device, result in results if result.get("is_anomaly") is not None]
    anomalous_devices = [device for device, result in ready if result["is_anomaly"]]
    have = max(
        (result.get("total_points_analyzed", result.get("have", 0)) for _, result in results),
        default=0,
    )
    return {
        "status": "ok" if ready else "not enough data",
        "min_required": 10,
        "have": have,
        "is_anomaly": bool(anomalous_devices),
        "anomalous_devices": anomalous_devices,
        "devices_analyzed": len(ready),
    }


@app.get("/predictions/forecast")
def get_forecast(
    hours: int = Query(default=1, ge=1, le=168),
    hostname: str | None = Query(default=None, min_length=1, max_length=255),
    db: Session = Depends(get_db),
):
    if hostname:
        return forecast_cpu(db, hours_ahead=hours, hostname=hostname)

    results = [
        (device, forecast_cpu(db, hours_ahead=hours, hostname=device))
        for device in metric_hostnames(db)
    ]
    forecasts = [(device, result) for device, result in results if "predicted_cpu_percent" in result]
    if not forecasts:
        return {
            "status": "not enough data",
            "min_required": 10,
            "have": max((result.get("have", 0) for _, result in results), default=0),
            "devices_analyzed": len(results),
        }

    device, forecast = max(forecasts, key=lambda item: item[1]["predicted_cpu_percent"])
    return {**forecast, "hostname": device, "devices_analyzed": len(forecasts)}


@app.get("/predictions/failure")
def get_failure_prediction(
    hostname: str | None = Query(default=None, min_length=1, max_length=255),
    db: Session = Depends(get_db),
):
    if hostname:
        return predict_failures(db, hostname=hostname)

    results = [
        (device, predict_failures(db, hostname=device))
        for device in metric_hostnames(db)
    ]
    if not results:
        return predict_failures(db)

    aggregated = {
        "samples_used": max(result["samples_used"] for _, result in results),
        "devices_analyzed": len(results),
    }
    for resource in ("cpu", "memory", "disk"):
        candidates = [
            (device, result[resource])
            for device, result in results
            if result[resource].get("status") != "not enough data"
        ]
        if not candidates:
            aggregated[resource] = {"status": "not enough data"}
            continue

        at_risk = [item for item in candidates if item[1].get("hours_to_limit") is not None]
        if at_risk:
            device, prediction = min(at_risk, key=lambda item: item[1]["hours_to_limit"])
        else:
            device, prediction = max(candidates, key=lambda item: item[1]["current"])
        aggregated[resource] = {**prediction, "hostname": device}
    return aggregated


@app.get("/alerts")
def get_alerts(
    hostname: str | None = Query(default=None, min_length=1, max_length=255),
    db: Session = Depends(get_db),
):
    return check_alerts(db, hostname=hostname)


@app.get("/alerts/history")
def alert_history(
    limit: int = Query(default=50, ge=1, le=500),
    hostname: str | None = Query(default=None, min_length=1, max_length=255),
    db: Session = Depends(get_db),
):
    query = db.query(AlertHistory)
    if hostname:
        query = query.filter(AlertHistory.hostname == hostname)
    return query.order_by(AlertHistory.timestamp.desc()).limit(limit).all()


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
def get_health_score(
    hostname: str | None = Query(default=None, min_length=1, max_length=255),
    db: Session = Depends(get_db),
):
    return calculate_health_score(db, hostname=hostname)


@app.post("/processes", status_code=201, dependencies=[Depends(verify_agent_key)])
def receive_processes(processes: list[ProcessIn] = Body(..., max_length=100), db: Session = Depends(get_db)):
    timestamp = utcnow()
    db.add_all([
        ProcessSnapshot(timestamp=timestamp, **process.model_dump())
        for process in processes
    ])
    db.commit()
    return {"status": "stored", "count": len(processes), "timestamp": timestamp}


@app.get("/processes")
def list_processes(
    limit: int = Query(default=10, ge=1, le=100),
    hostname: str | None = Query(default=None, min_length=1, max_length=255),
    db: Session = Depends(get_db),
):
    query = db.query(ProcessSnapshot)
    if hostname:
        query = query.filter(ProcessSnapshot.hostname == hostname)
    latest = query.with_entities(func.max(ProcessSnapshot.timestamp)).scalar()
    if latest is None:
        return []
    return (
        query.filter(ProcessSnapshot.timestamp == latest)
        .order_by(ProcessSnapshot.cpu_percent.desc())
        .limit(limit)
        .all()
    )


@app.get("/metrics/export")
def export_metrics(
    hostname: str | None = Query(default=None, min_length=1, max_length=255),
):
    def csv_rows():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "id",
            "timestamp",
            "hostname",
            "cpu_percent",
            "memory_percent",
            "disk_percent",
            "net_bytes_sent",
            "net_bytes_recv",
        ])
        yield output.getvalue()

        with SessionLocal() as export_db:
            query = export_db.query(Metric)
            if hostname:
                query = query.filter(Metric.hostname == hostname)
            rows = query.order_by(Metric.timestamp.asc(), Metric.id.asc()).yield_per(500)
            for row in rows:
                output.seek(0)
                output.truncate(0)
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
                yield output.getvalue()

    return StreamingResponse(
        csv_rows(),
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
