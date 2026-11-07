import numpy as np
from sqlalchemy.orm import Session

from db import Metric


def forecast_cpu(db: Session, hours_ahead: int = 1):
    rows = db.query(Metric).order_by(Metric.timestamp.asc()).all()
    if len(rows) < 10:
        return {"status": "not enough data", "min_required": 10, "have": len(rows)}

    timestamps = np.array([row.timestamp.timestamp() for row in rows], dtype=float)
    timestamps -= timestamps[0]
    values = np.array([row.cpu_percent for row in rows], dtype=float)
    if timestamps[-1] == 0:
        return {"status": "insufficient time span", "min_required_seconds": 1}

    slope, intercept = np.polyfit(timestamps, values, 1)
    predicted = float(np.clip(slope * (timestamps[-1] + hours_ahead * 3600) + intercept, 0, 100))
    return {
        "current_cpu": float(values[-1]),
        "predicted_cpu_in_hours": hours_ahead,
        "predicted_cpu_percent": round(predicted, 2),
        "trend": "increasing" if slope > 0.0001 else "decreasing" if slope < -0.0001 else "stable",
        "samples_used": len(rows),
    }
