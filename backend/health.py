from sqlalchemy.orm import Session
from db import Metric
from alerts import check_alerts

def calculate_health_score(db: Session):
    latest = db.query(Metric).order_by(Metric.timestamp.desc()).first()
    if not latest:
        return {"score": None, "status": "no data"}

    score = 100
    score -= max(0, latest.cpu_percent - 70) * 0.5
    score -= max(0, latest.memory_percent - 70) * 0.5
    score -= max(0, latest.disk_percent - 80) * 1.0

    alerts_data = check_alerts(db)
    score -= alerts_data["alert_count"] * 10

    score = max(0, min(100, round(score, 1)))

    if score >= 80:
        status = "healthy"
    elif score >= 50:
        status = "degraded"
    else:
        status = "critical"

    return {
        "score": score,
        "status": status,
        "active_alerts": alerts_data["alert_count"],
    } 