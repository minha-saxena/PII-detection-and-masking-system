"""
Core configuration for PII Masker application
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
import os


class Settings(BaseSettings):
    """Application settings"""
    
    # API Settings
    API_TITLE: str = "PII Detection & Masking API"
    API_VERSION: str = "1.0.0"
    API_DESCRIPTION: str = "Detect and mask PII in PDF documents using SLMs"
    
    # Ollama Settings
    OLLAMA_HOST: str = Field(default="http://localhost:11434", env="OLLAMA_HOST")
    OLLAMA_MODEL: str = Field(default="phi3.5", env="OLLAMA_MODEL")
    OLLAMA_TIMEOUT: int = 500  # seconds
    
    # File Settings
    DATA_DIR: str = "/app/data"
    UPLOAD_DIR: str = "/app/data/uploads"
    OUTPUT_DIR: str = "/app/data/outputs"
    TEMP_DIR: str = "/app/data/temp"
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB
    ALLOWED_EXTENSIONS: List[str] = [".pdf"]
    
    # Processing Settings
    CONFIDENCE_THRESHOLD: float = 0.7
    ENABLE_REGEX_DETECTOR: bool = True
    ENABLE_NER_DETECTOR: bool = True
    ENABLE_SLM_DETECTOR: bool = True
    
    # Regex Patterns
    REGEX_PATTERNS: dict = {
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "phone": r"\b(\+\d{1,2}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b",
        "credit_card": r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
    }
    
    # Default PII tags if user doesn't provide any
    DEFAULT_PII_TAGS: List[str] = [
        "name",
        "email",
        "phone",
        "ssn",
        "address",
        "credit_card"
    ]
    
    # Logging
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    
    # Cleanup
    CLEANUP_TEMP_FILES: bool = True
    FILE_RETENTION_HOURS: int = 24
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Create global settings instance
settings = Settings()


# Create directories if they don't exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
os.makedirs(settings.TEMP_DIR, exist_ok=True)