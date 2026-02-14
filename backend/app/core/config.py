from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Email Configuration for OTP
    mail_username: Optional[str] = ""
    mail_password: Optional[str] = ""
    mail_from: Optional[str] = "noreply@studyspace.com"
    mail_port: Optional[int] = 587
    mail_server: Optional[str] = "smtp.gmail.com"
    
    class Config:
        env_file = ".env"

settings = Settings()
