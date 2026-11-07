from datetime import timedelta

from db import Metric, utcnow


def sample_metric(**overrides):
    values = {
        "cpu_percent": 35.0,
        "memory_percent": 48.0,
        "disk_percent": 61.0,
        "net_bytes_sent": 1200,
        "net_bytes_recv": 5400,
    }
    values.update(overrides)
    return values


def test_health_and_empty_prediction_states(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/metrics/latest").json()["message"] == "No metrics recorded yet"
    assert client.get("/health/score").json() == {"score": None, "status": "no data"}
    assert client.get("/predictions/anomaly").json()["status"] == "not enough data"
    assert client.get("/predictions/forecast").json()["status"] == "not enough data"
    assert client.get("/alerts").json() == {"alert_count": 0, "alerts": []}


def test_metrics_are_validated_stored_and_exported(client):
    response = client.post("/metrics", json=sample_metric())
    assert response.status_code == 201
    assert response.json()["status"] == "stored"

    latest = client.get("/metrics/latest").json()
    assert latest["cpu_percent"] == 35
    assert client.get("/metrics/stats").json()["sample_count"] == 1

    invalid = client.post("/metrics", json=sample_metric(cpu_percent=101))
    assert invalid.status_code == 422

    export = client.get("/metrics/export")
    assert export.status_code == 200
    assert "cpu_percent" in export.text
    assert "35.0" in export.text


def test_alert_thresholds_can_be_updated_and_trigger_alerts(client):
    current = client.get("/alerts/config").json()
    assert current["cpu_threshold"] == 90

    saved = client.put("/alerts/config", json={
        "cpu_threshold": 80,
        "memory_threshold": 92,
        "disk_threshold": 85,
    })
    assert saved.status_code == 200
    assert saved.json()["cpu_threshold"] == 80
    assert client.post("/metrics", json=sample_metric(cpu_percent=84)).status_code == 201

    alerts = client.get("/alerts").json()
    assert alerts["alert_count"] == 1
    assert alerts["alerts"][0]["type"] == "threshold"
    assert client.get("/alerts/history").json()[0]["severity"] == "critical"


def test_process_snapshot_is_persisted_and_ranked(client):
    response = client.post("/processes", json=[
        {"pid": 101, "name": "worker", "cpu_percent": 12.5, "memory_percent": 5},
        {"pid": 102, "name": "browser", "cpu_percent": 62.0, "memory_percent": 15},
    ])
    assert response.status_code == 201
    assert response.json()["count"] == 2
    processes = client.get("/processes").json()
    assert processes[0]["name"] == "browser"
    assert client.post("/processes", json=[{"pid": -1, "name": "bad", "cpu_percent": 0, "memory_percent": 0}]).status_code == 422


def test_prediction_uses_sample_timestamps(db_session):
    start = utcnow() - timedelta(minutes=20)
    for index in range(12):
        db_session.add(Metric(
            timestamp=start + timedelta(minutes=index * 2),
            cpu_percent=20 + index * 2,
            memory_percent=30 + index,
            disk_percent=40 + index,
            net_bytes_sent=index * 100,
            net_bytes_recv=index * 200,
        ))
    db_session.commit()

    from forecast import forecast_cpu
    from failure import predict_failures

    forecast = forecast_cpu(db_session, hours_ahead=3)
    assert forecast["predicted_cpu_in_hours"] == 3
    assert forecast["predicted_cpu_percent"] > forecast["current_cpu"]
    assert predict_failures(db_session)["memory"]["trend"] == "increasing"
