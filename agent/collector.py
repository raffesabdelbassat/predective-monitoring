import psutil
import requests
import time

BACKEND_URL = "http://127.0.0.1:8000/metrics"
COLLECTION_INTERVAL_SECONDS = 10

def get_top_processes(limit=5):
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            processes.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    processes.sort(key=lambda p: p['cpu_percent'] or 0, reverse=True)
    return processes[:limit]   

def collect_metrics() -> dict:
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("C:\\")
    net = psutil.net_io_counters()
    top_processes = get_top_processes()

    return {
        "cpu_percent": cpu_percent,
        "memory_percent": memory.percent,
        "disk_percent": disk.percent,
        "net_bytes_sent": net.bytes_sent,
        "net_bytes_recv": net.bytes_recv,
        "top_processes": top_processes,
    }

def send_metrics(metrics: dict):
    top_processes = metrics.pop("top_processes", [])
    response = requests.post(BACKEND_URL, json=metrics, timeout=5)
    print(f"Sent metrics, backend responded: {response.json()}")

    if top_processes:
        try:
            requests.post("http://127.0.0.1:8000/processes", json=top_processes, timeout=5)
        except requests.exceptions.RequestException as e:
            print(f"Failed to send processes: {e}")

def run():
    print("Agent started. Press Ctrl+C to stop.")
    while True:
        metrics = collect_metrics()
        send_metrics(metrics)
        time.sleep(COLLECTION_INTERVAL_SECONDS)

if __name__ == "__main__":
    run()