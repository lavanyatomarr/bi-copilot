from sqlalchemy import Boolean, Column, DateTime, Integer, String, func

from ..db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)   # NEVER the raw password
    role = Column(String, nullable=False, default="analyst")  # 'analyst' | 'admin'
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
