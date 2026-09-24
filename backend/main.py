from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from db import Base, engine, get_db, Metric
from schemas import MetricIn 
from sqlalchemy import func
from ai import detect_anomalies

from forecast import forecast_cpu
from alerts import check_alerts
from fastapi import WebSocket, WebSocketDisconnect
import asyncio
import json

from fastapi import Body
 
app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
Base.metadata.create_all(bind=engine)

@app.get("/")
def read_root():
    return {"message": "Predictive Monitoring API is running"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/status/{service_name}")
def service_status(service_name: str):
    return {"service": service_name, "status": "monitoring not yet implemented"}
@app.post("/metrics")
def receive_metrics(metrics: MetricIn, db: Session = Depends(get_db)):
    db_metric = Metric(
        cpu_percent=metrics.cpu_percent,
        memory_percent=metrics.memory_percent,
        disk_percent=metrics.disk_percent,
        net_bytes_sent=metrics.net_bytes_sent,
        net_bytes_recv=metrics.net_bytes_recv,
    )
    db.add(db_metric)
    db.commit()
    db.refresh(db_metric)
    print(f"Stored metric id={db_metric.id}")
    return {"status": "stored", "id": db_metric.id}

@app.get("/metrics")
def list_metrics(db: Session = Depends(get_db)):
    metrics = db.query(Metric).order_by(Metric.timestamp.desc()).limit(10).all()
    return metrics 

@app.get("/metrics/latest")
def latest_metric(db: Session = Depends(get_db)):
    metric = db.query(Metric).order_by(Metric.timestamp.desc()).first()
    if metric is None:
        return {"message": "No metrics recorded yet"}
    return metric

@app.get("/predictions/anomaly")
def get_anomaly_check(db: Session = Depends(get_db)):
    return detect_anomalies(db) 

@app.get("/metrics/stats")
def metrics_stats(db: Session = Depends(get_db)):
    result = db.query(
        func.avg(Metric.cpu_percent),
        func.avg(Metric.memory_percent),
        func.avg(Metric.disk_percent),
    ).first()

    return {
        "avg_cpu_percent": round(result[0], 2) if result[0] else None,
        "avg_memory_percent": round(result[1], 2) if result[1] else None,
        "avg_disk_percent": round(result[2], 2) if result[2] else None,
    } 
@app.get("/predictions/forecast")
def get_forecast(hours: int = 1, db: Session = Depends(get_db)):
    return forecast_cpu(db, hours_ahead=hours)  

@app.get("/alerts")
def get_alerts(db: Session = Depends(get_db)):
    return check_alerts(db) 
@app.websocket("/ws/metrics")
async def websocket_metrics(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            db = next(get_db())
            latest = db.query(Metric).order_by(Metric.timestamp.desc()).first()
            alerts_data = check_alerts(db)
            db.close()

            if latest:
                payload = {
                    "cpu_percent": latest.cpu_percent,
                    "memory_percent": latest.memory_percent,
                    "disk_percent": latest.disk_percent,
                    "timestamp": latest.timestamp.isoformat(),
                    "alert_count": alerts_data["alert_count"],
                }
                await websocket.send_text(json.dumps(payload))

            await asyncio.sleep(5)
    except WebSocketDisconnect:
        pass 


    from db import AlertHistory

@app.get("/alerts/history")
def alert_history(db: Session = Depends(get_db)):
    history = db.query(AlertHistory).order_by(AlertHistory.timestamp.desc()).limit(50).all()
    return history 

@app.post("/processes")
def receive_processes(processes: list[dict] = Body(...)):
    return {"status": "received", "count": len(processes)}