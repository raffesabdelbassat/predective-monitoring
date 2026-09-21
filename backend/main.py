from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from db import Base, engine, get_db, Metric

app = FastAPI()

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
def receive_metrics(metrics: dict, db: Session = Depends(get_db)):
    db_metric = Metric(
        cpu_percent=metrics["cpu_percent"],
        memory_percent=metrics["memory_percent"],
    )
    db.add(db_metric)
    db.commit()
    db.refresh(db_metric)
    print(f"Stored metric id={db_metric.id}: {metrics}")
    return {"status": "stored", "id": db_metric.id}