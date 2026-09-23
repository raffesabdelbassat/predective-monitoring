from sqlalchemy import create_engine, Column, Integer, Float, DateTime, BigInteger
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, Float, DateTime, BigInteger, String
import os
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://monitor_user:monitor_pass@127.0.0.1:5433/monitor_db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Metric(Base):
    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    cpu_percent = Column(Float, nullable=False)
    memory_percent = Column(Float, nullable=False)
    disk_percent = Column(Float, nullable=False)
    net_bytes_sent = Column(BigInteger, nullable=False)
    net_bytes_recv = Column(BigInteger, nullable=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()