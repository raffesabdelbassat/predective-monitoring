import os
import sys
import time

import psutil
import requests


BACKEND_URL = os.getenv(
    "BACKEND_URL",
    os.getenv("MONITORING_API_URL", "http://127.0.0.1:8000"),
).rstrip("/")
COLLECTION_INTERVAL_SECONDS = max(2, int(os.getenv("COLLECTION_INTERVAL_SECONDS", "10")))


def get_top_processes(limit=5):
    processes = []
    for process in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            processes.append(process.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    processes.sort(key=lambda process: process.get("cpu_percent") or 0, reverse=True)
    return processes[:limit]


def collect_metrics() -> dict:
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(os.path.abspath(os.sep))
    network = psutil.net_io_counters()
    return {
        "cpu_percent": cpu_percent,
        "memory_percent": memory.percent,
        "disk_percent": disk.percent,
        "net_bytes_sent": network.bytes_sent,
        "net_bytes_recv": network.bytes_recv,
        "top_processes": get_top_processes(),
    }


def send_metrics(metrics: dict):
    metric_payload = {key: value for key, value in metrics.items() if key != "top_processes"}
    response = requests.post(f"{BACKEND_URL}/metrics", json=metric_payload, timeout=5)
    response.raise_for_status()
    print(f"Sent metric, backend responded: {response.json()}")

    processes = metrics.get("top_processes", [])
    if processes:
        process_payload = [
            {
                "pid": process["pid"],
                "name": process.get("name") or "Unknown",
                "cpu_percent": process.get("cpu_percent") or 0,
                "memory_percent": process.get("memory_percent") or 0,
            }
            for process in processes
            if process.get("pid") is not None
        ]
        response = requests.post(f"{BACKEND_URL}/processes", json=process_payload, timeout=5)
        response.raise_for_status()


def run():
    print(f"Agent started. Sending metrics to {BACKEND_URL}. Press Ctrl+C to stop.")
    while True:
        try:
            send_metrics(collect_metrics())
        except requests.exceptions.RequestException as error:
            print(f"Could not send metrics: {error}", file=sys.stderr)
        except (psutil.Error, OSError) as error:
            print(f"Could not collect system metrics: {error}", file=sys.stderr)
        time.sleep(COLLECTION_INTERVAL_SECONDS)


if __name__ == "__main__":
    run()
