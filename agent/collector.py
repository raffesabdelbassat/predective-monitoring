import psutil
import requests
import time

BACKEND_URL = "http://127.0.0.1:8000/metrics"
COLLECTION_INTERVAL_SECONDS = 10

def collect_metrics() -> dict:
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("C:\\")
    net = psutil.net_io_counters()

    return {
        "cpu_percent": cpu_percent,
        "memory_percent": memory.percent,
        "disk_percent": disk.percent,
        "net_bytes_sent": net.bytes_sent,
        "net_bytes_recv": net.bytes_recv,
    }

def send_metrics(metrics: dict):
    response = requests.post(BACKEND_URL, json=metrics, timeout=5)
    print(f"Sent metrics, backend responded: {response.json()}")

def run():
    print("Agent started. Press Ctrl+C to stop.")
    while True:
        metrics = collect_metrics()
        send_metrics(metrics)
        time.sleep(COLLECTION_INTERVAL_SECONDS)

if __name__ == "__main__":
    run()