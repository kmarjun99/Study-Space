"""Frozen copy of `tax_config` at the moment of a financial event.

Persisted so that years later a CA can reproduce the exact computation that
generated an invoice / ledger entry, even after the live config has changed.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text
from app.database import Base


class TaxSnapshot(Base):
    __tablename__ = "tax_snapshots"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    snapshot_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    payload = Column(Text, nullable=False)   # JSON-encoded dict of tax_config keys -> values
