"""Frozen party (legal name, address, GSTIN, state) snapshot used by issued documents.

Existing user / owner records change over time. Once an invoice is issued, the
party data on it must never mutate. We persist a `parties` row at issuance and
reference it from `invoices`.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text
from app.database import Base


class Party(Base):
    __tablename__ = "parties"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    party_type = Column(String(20), nullable=False)         # PLATFORM / OWNER / STUDENT
    party_ref_id = Column(String, nullable=True, index=True)  # FK to users.id where applicable

    legal_name = Column(String(255), nullable=False)
    address = Column(Text, nullable=True)
    gstin = Column(String(15), nullable=True)
    pan = Column(String(10), nullable=True)
    state_code = Column(String(2), nullable=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(20), nullable=True)

    snapshot_at = Column(DateTime, default=datetime.utcnow, nullable=False)
