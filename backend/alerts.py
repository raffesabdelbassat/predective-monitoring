from sqlalchemy.orm import Session
from db import Metric
from ai import detect_anomalies
from forecast import forecast_cpu
from db import AlertHistory
from datetime import datetime

def check_alerts(db: Session):
    alerts = []

    anomaly_result = detect_anomalies(db)
    if anomaly_result.get("is_anomaly"):
        alerts.append({
            "type": "anomaly",
            "severity": "warning",
            "message": f"Unusual system behavior detected — CPU {anomaly_result['latest_cpu']}%, "
                       f"Memory {anomaly_result['latest_memory']}%, Disk {anomaly_result['latest_disk']}%"
        })

    forecast_result = forecast_cpu(db, hours_ahead=1)
    predicted_cpu = forecast_result.get("predicted_cpu_percent")
    if predicted_cpu is not None and predicted_cpu > 90:
        alerts.append({
            "type": "forecast",
            "severity": "critical",
            "message": f"CPU usage trending toward {predicted_cpu}% within the next hour. "
                       f"Possible overload risk."
        })

    latest = db.query(Metric).order_by(Metric.timestamp.desc()).first()
    if latest:
        if latest.disk_percent > 90:
            alerts.append({
                "type": "threshold",
                "severity": "critical",
                "message": f"Disk usage at {latest.disk_percent}% — approaching capacity."
            })
        if latest.memory_percent > 95:
            alerts.append({
                "type": "threshold",
                "severity": "critical",
                "message": f"Memory usage at {latest.memory_percent}% — system may become unresponsive."
            })
            for alert in alerts:
        existing = db.query(AlertHistory).filter(
            AlertHistory.message == alert["message"]
        ).order_by(AlertHistory.timestamp.desc()).first()

        if not existing or (datetime.utcnow() - existing.timestamp).total_seconds() > 300:
            db_alert = AlertHistory(
                alert_type=alert["type"],
                severity=alert["severity"],
                message=alert["message"],
            )
            db.add(db_alert)
    db.commit()

    return {
        "alert_count": len(alerts),
        "alerts": alerts,
    }