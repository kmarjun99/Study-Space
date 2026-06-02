"""Atomic counter per (series_code, fiscal_year).

Replaces the timestamp-mod numbering in models/invoice.py — which is not
collision-safe under concurrency. Allocation uses SELECT ... FOR UPDATE.
"""
from sqlalchemy import Column, String, Integer, PrimaryKeyConstraint
from app.database import Base


class InvoiceSeriesCounter(Base):
    __tablename__ = "invoice_series_counter"

    series_code = Column(String(10), nullable=False)   # PLF / OBI / ECO / RCT / CN / STM
    fiscal_year = Column(String(7), nullable=False)    # e.g. '25-26'
    last_no = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        PrimaryKeyConstraint("series_code", "fiscal_year"),
    )
