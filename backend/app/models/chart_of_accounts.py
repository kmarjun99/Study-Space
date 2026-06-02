"""Chart of accounts — small reference table used by the double-entry ledger."""
from sqlalchemy import Column, String, Boolean
from app.database import Base


class ChartOfAccounts(Base):
    __tablename__ = "chart_of_accounts"

    code = Column(String(10), primary_key=True)
    name = Column(String(120), nullable=False)
    type = Column(String(20), nullable=False)   # ASSET, LIABILITY, INCOME, EXPENSE, EQUITY
    normal_side = Column(String(2), nullable=False)  # 'Dr' or 'Cr'
    is_active = Column(Boolean, default=True, nullable=False)
