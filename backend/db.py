import os
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Column, DateTime, Float, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://monitor_user:monitor_pass@127.0.0.1:5433/monitor_db",
)
engine_options = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}
    if ":memory:" in DATABASE_URL:
        engine_options["poolclass"] = StaticPool

engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Metric(Base):
    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=utcnow, nullable=False, index=True)
    cpu_percent = Column(Float, nullable=False)
    memory_percent = Column(Float, nullable=False)
    disk_percent = Column(Float, nullable=False)
    net_bytes_sent = Column(BigInteger, nullable=False)
    net_bytes_recv = Column(BigInteger, nullable=False)


class ProcessSnapshot(Base):
    __tablename__ = "process_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=utcnow, nullable=False, index=True)
    pid = Column(Integer, nullable=False)
    name = Column(String(255), nullable=False)
    cpu_percent = Column(Float, nullable=False)
    memory_percent = Column(Float, nullable=False)


class AlertHistory(Base):
    __tablename__ = "alert_history"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=utcnow, nullable=False, index=True)
    alert_type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)
    message = Column(String, nullable=False)


class AlertConfig(Base):
    __tablename__ = "alert_config"

    id = Column(Integer, primary_key=True, index=True)
    cpu_threshold = Column(Float, nullable=False, default=90.0)
    memory_threshold = Column(Float, nullable=False, default=95.0)
    disk_threshold = Column(Float, nullable=False, default=90.0)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
