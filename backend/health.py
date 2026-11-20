from sqlalchemy.orm import Session
from db import METRIC_STALE_AFTER, Metric, utcnow
from alerts import check_alerts

def calculate_health_score(db: Session, hostname: str | None = None):
    if hostname is None:
        hostnames = [
            row[0]
            for row in db.query(Metric.hostname).distinct().order_by(Metric.hostname).all()
            if row[0]
        ]
        scores = [calculate_health_score(db, hostname=device_hostname) for device_hostname in hostnames]
        if not scores:
            return {"score": None, "status": "no data"}

        status_order = {"critical": 0, "degraded": 1, "stale": 2, "healthy": 3}
        weakest = min(scores, key=lambda item: (status_order[item["status"]], item["score"]))
        return {
            "score": weakest["score"],
            "status": weakest["status"],
            "active_alerts": sum(item["active_alerts"] for item in scores),
        }

    query = db.query(Metric)
    query = query.filter(Metric.hostname == hostname)
    latest = query.order_by(Metric.timestamp.desc()).first()
    if not latest:
        return {"score": None, "status": "no data"}

    telemetry_is_stale = latest.timestamp < utcnow() - METRIC_STALE_AFTER

    score = 100
    score -= max(0, latest.cpu_percent - 70) * 0.5
    score -= max(0, latest.memory_percent - 70) * 0.5
    score -= max(0, latest.disk_percent - 80) * 1.0

    alerts_data = check_alerts(db, hostname=hostname)
    score -= alerts_data["alert_count"] * 10

    score = max(0, min(100, round(score, 1)))

    if telemetry_is_stale:
        status = "stale"
    elif score >= 80:
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
