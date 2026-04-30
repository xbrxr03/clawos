# SPDX-License-Identifier: AGPL-3.0-or-later
"""Structured JSON logging with rotation for all ClawOS services."""
import json
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(service_name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Setup structured JSON logging for a service.
    
    Outputs:
    - Console: human-readable format
    - File: JSON lines with rotation (10MB, 5 files)
    """
    logger = logging.getLogger(service_name)
    logger.setLevel(level)
    logger.handlers = []  # Clear existing
    
    # Console handler - human readable
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console_fmt = logging.Formatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console.setFormatter(console_fmt)
    logger.addHandler(console)
    
    # File handler - JSON with rotation
    log_dir = Path.home() / ".clawos-runtime" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{service_name}.log"
    
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(level)
    
    # JSON formatter
    class JSONFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            log_obj = {
                "timestamp": self.formatTime(record),
                "service": record.name,
                "level": record.levelname,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
            }
            if record.exc_info:
                log_obj["exception"] = self.formatException(record.exc_info)
            return json.dumps(log_obj)
    
    file_handler.setFormatter(JSONFormatter())
    logger.addHandler(file_handler)
    
    return logger
