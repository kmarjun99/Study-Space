"""Configurable tax / accounting settings.

Values stored as JSON strings (TEXT) for broad DB compatibility (SQLite + Postgres).
Service layer parses to native types.
"""
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text
from app.database import Base


class TaxConfig(Base):
    __tablename__ = "tax_config"

    key = Column(String(80), primary_key=True)
    value = Column(Text, nullable=False)            # JSON-encoded
    description = Column(String(255), nullable=True)
    updated_by = Column(String, nullable=True)      # user id of super admin
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
