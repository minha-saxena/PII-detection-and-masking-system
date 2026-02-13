"""
Logging configuration using loguru
"""
from loguru import logger
import sys
from core.config import settings


def setup_logger():
    """Configure logger with custom format and level"""
    
    # Remove default handler
    logger.remove()
    
    # Add custom handler with formatting
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.LOG_LEVEL,
        colorize=True
    )
    
    # Add file handler for errors
    logger.add(
        "/app/data/logs/error.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="ERROR",
        rotation="10 MB",
        retention="7 days",
        compression="zip"
    )
    
    return logger


# Initialize logger
log = setup_logger()