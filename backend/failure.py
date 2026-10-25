import numpy as np
from sqlalchemy.orm import Session
from db import Metric

def _time_to_limit(timestamps, values, limit=100.0):
    if len(values) < 10:
        return {"status": "not enough data"}

    x = np.array([t.timestamp() for t in timestamps])
    x = x - x[0]
    y = np.array(values, dtype=float)

    slope, intercept = np.polyfit(x, y, 1)
    fitted = slope * x + intercept
    ss_res = float(np.sum((y - fitted) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

    slope_per_hour = slope * 3600
    result = {
        "current": round(float(y[-1]), 2),
        "slope_per_hour": round(float(slope_per_hour), 3),
        "trend_confidence": round(max(0.0, r2), 2),
    }

    if slope_per_hour <= 0.01:
        result["trend"] = "stable_or_decreasing"
        result["hours_to_limit"] = None
    else:
        hours_left = (limit - y[-1]) / slope_per_hour
        result["trend"] = "increasing"
        result["hours_to_limit"] = round(max(0.0, float(hours_left)), 1)

    return result

def predict_failures(db: Session, window: int = 200):
    rows = (
        db.query(Metric)
        .order_by(Metric.timestamp.desc())
        .limit(window)
        .all()
    )
    rows.reverse()

    timestamps = [r.timestamp for r in rows]
    return {
        "samples_used": len(rows),
        "memory": _time_to_limit(timestamps, [r.memory_percent for r in rows]),
        "disk": _time_to_limit(timestamps, [r.disk_percent for r in rows]),
        "cpu": _time_to_limit(timestamps, [r.cpu_percent for r in rows]),
    }