from pydantic import BaseModel, Field


class MetricIn(BaseModel):
    hostname: str = Field(default="localhost", min_length=1, max_length=255)
    cpu_percent: float = Field(ge=0, le=100)
    memory_percent: float = Field(ge=0, le=100)
    disk_percent: float = Field(ge=0, le=100)
    net_bytes_sent: int = Field(ge=0)
    net_bytes_recv: int = Field(ge=0)


class ProcessIn(BaseModel):
    pid: int = Field(ge=0)
    name: str = Field(min_length=1, max_length=255)
    cpu_percent: float = Field(ge=0)
    memory_percent: float = Field(ge=0, le=100)


class AlertConfigIn(BaseModel):
    cpu_threshold: float = Field(ge=1, le=100)
    memory_threshold: float = Field(ge=1, le=100)
    disk_threshold: float = Field(ge=1, le=100)
