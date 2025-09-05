"""Structured logging with redaction helpers."""

import logging
import json
import re
from typing import Any, Dict, List
from datetime import datetime

# Sensitive key patterns to redact
SENSITIVE_PATTERNS = [
    r"api[_-]?key",
    r"token",
    r"secret",
    r"password",
    r"credential",
    r"auth",
    r"zsessionid"
]


class StructuredFormatter(logging.Formatter):
    """JSON structured log formatter."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra fields
        if hasattr(record, "agent"):
            log_obj["agent"] = record.agent
        if hasattr(record, "tool"):
            log_obj["tool"] = record.tool
        if hasattr(record, "session_id"):
            log_obj["session_id"] = record.session_id
        if hasattr(record, "user_id"):
            log_obj["user_id"] = record.user_id
        if hasattr(record, "event_id"):
            log_obj["event_id"] = record.event_id
            
        # Add exception info if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_obj)


def redact_sensitive(data: Any) -> Any:
    """Redact sensitive information from data.
    
    Args:
        data: Data to redact (dict, list, or string)
    
    Returns:
        Redacted data
    """
    if isinstance(data, dict):
        return {k: redact_value(k, v) for k, v in data.items()}
    elif isinstance(data, list):
        return [redact_sensitive(item) for item in data]
    elif isinstance(data, str):
        # Redact tokens in strings
        for pattern in SENSITIVE_PATTERNS:
            data = re.sub(
                rf"({pattern})[\s=:]*[\S]+",
                r"\1=***REDACTED***",
                data,
                flags=re.IGNORECASE
            )
        return data
    return data


def redact_value(key: str, value: Any) -> Any:
    """Redact value if key matches sensitive pattern.
    
    Args:
        key: Dictionary key
        value: Value to potentially redact
    
    Returns:
        Original or redacted value
    """
    key_lower = key.lower()
    for pattern in SENSITIVE_PATTERNS:
        if re.search(pattern, key_lower):
            return "***REDACTED***"
    
    # Recursively redact nested structures
    if isinstance(value, (dict, list)):
        return redact_sensitive(value)
    
    return value


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance.
    
    Args:
        name: Logger name (usually __name__)
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def setup_logging(
    level: str = "INFO",
    structured: bool = True
) -> None:
    """Set up application logging.
    
    Args:
        level: Log level
        structured: Use structured JSON logging
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level))
    
    # Clear existing handlers
    root_logger.handlers = []
    
    # Create console handler
    handler = logging.StreamHandler()
    
    if structured:
        handler.setFormatter(StructuredFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        )
    
    root_logger.addHandler(handler)
    
    # Suppress noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)