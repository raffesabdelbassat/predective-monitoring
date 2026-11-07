from datetime import timedelta

from sqlalchemy.orm import Session

from ai import detect_anomalies
from db import AlertConfig, AlertHistory, Metric, utcnow
from failure import predict_failures
from forecast import forecast_cpu


def get_alert_config(db: Session) -> AlertConfig:
    config = db.query(AlertConfig).order_by(AlertConfig.id.asc()).first()
    if config is None:
        config = AlertConfig()
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def check_alerts(db: Session):
    alerts = []
    latest = db.query(Metric).order_by(Metric.timestamp.desc()).first()
    if latest is None:
        return {"alert_count": 0, "alerts": []}

    config = get_alert_config(db)
    anomaly_result = detect_anomalies(db)
    if anomaly_result.get("is_anomaly"):
        alerts.append({
            "type": "anomaly",
            "severity": "warning",
            "message": (
                "Unusual system behavior detected — "
                f"CPU {anomaly_result['latest_cpu']}%, "
                f"Memory {anomaly_result['latest_memory']}%, "
                f"Disk {anomaly_result['latest_disk']}%"
            ),
        })

    forecast_result = forecast_cpu(db, hours_ahead=1)
    predicted_cpu = forecast_result.get("predicted_cpu_percent")
    if predicted_cpu is not None and predicted_cpu >= config.cpu_threshold:
        alerts.append({
            "type": "forecast",
            "severity": "critical",
            "message": f"CPU is forecast to reach {predicted_cpu}% within the next hour.",
        })

    for resource, value, threshold in (
        ("CPU", latest.cpu_percent, config.cpu_threshold),
        ("Memory", latest.memory_percent, config.memory_threshold),
        ("Disk", latest.disk_percent, config.disk_threshold),
    ):
        if value >= threshold:
            alerts.append({
                "type": "threshold",
                "severity": "critical",
                "message": f"{resource} usage is {value}% (threshold {threshold}%).",
            })

    predictions = predict_failures(db)
    for resource, warning_hours, severity in (("memory", 6, "critical"), ("disk", 24, "warning")):
        prediction = predictions[resource]
        hours_to_limit = prediction.get("hours_to_limit")
        if (
            hours_to_limit is not None
            and hours_to_limit < warning_hours
            and prediction.get("trend_confidence", 0) > 0.5
        ):
            alerts.append({
                "type": "prediction",
                "severity": severity,
                "message": (
                    f"{resource.capitalize()} usage is trending upward; "
                    f"estimated limit in {hours_to_limit} hours "
                    f"(confidence {prediction['trend_confidence']})."
                ),
            })

    now = utcnow()
    for alert in alerts:
        existing = (
            db.query(AlertHistory)
            .filter(AlertHistory.message == alert["message"])
            .order_by(AlertHistory.timestamp.desc())
            .first()
        )
        if existing is None or now - existing.timestamp > timedelta(minutes=5):
            db.add(AlertHistory(
                alert_type=alert["type"],
                severity=alert["severity"],
                message=alert["message"],
            ))
    db.commit()

    return {"alert_count": len(alerts), "alerts": alerts}
