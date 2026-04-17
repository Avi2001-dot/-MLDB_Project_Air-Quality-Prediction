import logging
import logging.handlers
import os
from typing import Optional
from datetime import datetime

from .constants import (
    LOG_FORMAT,
    LOG_MAX_BYTES,
    LOG_BACKUP_COUNT,
    LOG_LEVELS,
    DEFAULT_LOG_LEVEL
)


class LoggerConfig:
    """Configuration class for system logging."""

    _logger_instance: Optional[logging.Logger] = None
    _initialized = False

    @classmethod
    def setup_logging(
        cls,
        log_level: str = DEFAULT_LOG_LEVEL,
        log_file: str = 'logs/system.log',
        log_format: str = LOG_FORMAT
    ) -> logging.Logger:
        
        if log_level not in LOG_LEVELS:
            raise ValueError(
                f"Invalid log level: {log_level}. "
                f"Must be one of {LOG_LEVELS}"
            )

        # Create logs directory if it doesn't exist
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        # Get root logger
        logger = logging.getLogger('aqi_system')
        logger.setLevel(getattr(logging, log_level))

        # Remove existing handlers to avoid duplicates
        if logger.handlers:
            for handler in logger.handlers:
                logger.removeHandler(handler)

        # Create formatter
        formatter = logging.Formatter(log_format)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, log_level))
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # File handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        cls._logger_instance = logger
        cls._initialized = True

        logger.info(f"Logging initialized at {datetime.now()}")
        logger.info(f"Log level: {log_level}")
        logger.info(f"Log file: {log_file}")

        return logger

    @classmethod
    def get_logger(cls) -> logging.Logger:
        
        if not cls._initialized or cls._logger_instance is None:
            raise RuntimeError(
                "Logger not initialized. Call setup_logging() first."
            )
        return cls._logger_instance

    @classmethod
    def get_module_logger(cls, module_name: str) -> logging.Logger:
        
        if not cls._initialized:
            cls.setup_logging()

        return logging.getLogger(f'aqi_system.{module_name}')


def get_logger(module_name: str = 'aqi_system') -> logging.Logger:
    
    if not LoggerConfig._initialized:
        LoggerConfig.setup_logging()

    return logging.getLogger(f'aqi_system.{module_name}')


def setup_logging(
    log_level: str = DEFAULT_LOG_LEVEL,
    log_file: str = 'logs/system.log'
) -> logging.Logger:
    
    return LoggerConfig.setup_logging(log_level, log_file)


# Initialize logging on module import
if not LoggerConfig._initialized:
    try:
        setup_logging()
    except Exception as e:
        # Fallback to basic logging if setup fails
        logging.basicConfig(
            level=logging.INFO,
            format=LOG_FORMAT
        )
