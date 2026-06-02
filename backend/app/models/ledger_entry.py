"""Append-only double-entry ledger rows.

Each balanced business event is a `txn_group_id` containing >= 2 rows whose
debits equal credits. Never UPDATE or DELETE a row after posting; corrections
are issued as reversing entries with a fresh `txn_group_id`.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Numeric, Index, CheckConstraint
from app.database import Base


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    txn_group_id = Column(String, nullable=False, index=True)
    account_code = Column(String(10), nullable=False, index=True)

    party_type = Column(String(20), nullable=True)   # 'USER','OWNER','STUDENT','PLATFORM'
    party_id = Column(String, nullable=True, index=True)

    debit = Column(Numeric(14, 2), nullable=False, default=0)
    credit = Column(Numeric(14, 2), nullable=False, default=0)
    currency = Column(String(3), nullable=False, default="INR")

    source_type = Column(String(30), nullable=False)  # BOOKING, OWNER_CHARGE, REFUND, SETTLEMENT, ADJUSTMENT
    source_id = Column(String, nullable=False, index=True)

    narration = Column(String(255), nullable=True)
    posted_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        # Exactly one of (debit, credit) is non-zero — XOR enforced at service layer too.
        CheckConstraint(
            "(debit = 0 AND credit > 0) OR (debit > 0 AND credit = 0)",
            name="ck_ledger_entry_xor",
        ),
        Index("ix_ledger_account_party", "account_code", "party_id"),
    )
