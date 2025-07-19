import os
from typing import List, Optional
from pydantic import validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration settings loaded from environment variables."""
    
    # Telegram configuration
    telegram_token: str
    webhook_url: str
    
    # OpenAI configuration
    openai_api_key: str
    
    # Authentication
    shared_secret: str
    allowed_user_ids: str
    
    # Server configuration
    port: int = 8000
    host: str = "0.0.0.0"
    
    # Storage configuration
    transcripts_file: str = "transcripts.jsonl"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
    
    @validator('allowed_user_ids')
    def parse_allowed_user_ids(cls, v):
        """Parse comma-separated user IDs into a list of integers."""
        if isinstance(v, str):
            return [int(uid.strip()) for uid in v.split(',') if uid.strip()]
        return v
    
    @property
    def allowed_user_ids_list(self) -> List[int]:
        """Get the allowed user IDs as a list of integers."""
        return self.allowed_user_ids


def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()


settings = get_settings()