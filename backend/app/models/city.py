from sqlalchemy import Column, String, Boolean, DateTime
from app.database import Base
from datetime import datetime

class CitySettings(Base):
    __tablename__ = "city_settings"

    city_name = Column(String, primary_key=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
