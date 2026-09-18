from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Predictive Monitoring API is running"}

@app.get("/health")
def health_check():
    return {"status": "ok"} 

@app.get("/status/{service_name}")
def service_status(service_name: str):
    return {"service": service_name, "status": "monitoring not yet implemented"} 

@app.post("/metrics")
def receive_metrics(metrics: dict):
    print(f"Received metrics: {metrics}")
    return {"status": "received"}  