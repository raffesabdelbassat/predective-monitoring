import numpy as np
from sqlalchemy.orm import Session
from db import Metric

def forecast_cpu(db: Session, hours_ahead: int = 1):
    rows = db.query(Metric).order_by(Metric.timestamp.asc()).all()
    if len(rows) < 10:
        return {"status": "not enough data", "min_required": 10, "have": len(rows)}

    y = np.array([r.cpu_percent for r in rows])
    x = np.arange(len(y))

    coeffs = np.polyfit(x, y, 1)
    slope, intercept = coeffs

    future_x = len(y) + (hours_ahead * 360)
    predicted = slope * future_x + intercept
    predicted = max(0, min(100, predicted))

    return {
        "current_cpu": float(y[-1]),
        "predicted_cpu_in_hours": hours_ahead,
        "predicted_cpu_percent": round(float(predicted), 2),
        "trend": "increasing" if slope > 0 else "decreasing" if slope < 0 else "stable",
    }