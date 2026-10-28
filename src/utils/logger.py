"""
Centralized logging configuration using RichHandler for structured, colored console logs.
"""

import logging
import sys
from rich.logging import RichHandler
from src.config import settings


def setup_logger(name: str = "placidway") -> logging.Logger:
    """
    Configure and return a standardized logger with RichHandler.
    Respects LOG_LEVEL from environment settings.
    """
    logger = logging.getLogger(name)
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(log_level)

    if not logger.handlers:
        handler = RichHandler(
            console=None,
            rich_tracebacks=True,
            tracebacks_show_locals=False,
            markup=True,
            show_time=True,
            show_path=False,
        )
        handler.setFormatter(logging.Formatter("%(message)s", datefmt="[%X]"))
        logger.addHandler(handler)
        logger.propagate = False

    return logger


def get_logger(module_name: str) -> logging.Logger:
    """Convenience function to get a module-specific child logger."""
    return setup_logger(f"placidway.{module_name}")
