import pandas as pd
from sklearn.ensemble import IsolationForest
from sqlalchemy.orm import Session
from db import Metric

def detect_anomalies(db: Session):
    rows = db.query(Metric).order_by(Metric.timestamp.asc()).all()
    if len(rows) < 10:
        return {"status": "not enough data", "min_required": 10, "have": len(rows)}

    df = pd.DataFrame([{
        "cpu_percent": r.cpu_percent,
        "memory_percent": r.memory_percent,
        "disk_percent": r.disk_percent,
    } for r in rows])

    model = IsolationForest(contamination=0.1, random_state=42)
    df["anomaly"] = model.fit_predict(df[["cpu_percent", "memory_percent", "disk_percent"]])

    latest = df.iloc[-1]
    is_anomaly = latest["anomaly"] == -1

    return {
        "is_anomaly": bool(is_anomaly),
        "latest_cpu": latest["cpu_percent"],
        "latest_memory": latest["memory_percent"],
        "latest_disk": latest["disk_percent"],
        "total_points_analyzed": len(df),
        "total_anomalies_found": int((df["anomaly"] == -1).sum()),
    }