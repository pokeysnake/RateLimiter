from sqlalchemy import Column, Integer, String, DateTime, func
from app.db import Base


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True)
    key_hash = Column(String, unique=True, index=True, nullable=False)
    algorithm = Column(String, nullable=False)
    capacity = Column(Integer, nullable=False)
    window_seconds = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
