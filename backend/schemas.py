from pydantic import BaseModel

class MetricIn(BaseModel):
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    net_bytes_sent: int
    net_bytes_recv: int
