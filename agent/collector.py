import psutil

def collect_metrics() -> dict:
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()

    return {
        "cpu_percent": cpu_percent,
        "memory_percent": memory.percent,
    }

if __name__ == "__main__":
    metrics = collect_metrics()
    print(metrics) 
    