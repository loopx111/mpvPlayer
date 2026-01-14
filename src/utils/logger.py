import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from .paths import logs_dir


def setup_logging(level: str = "INFO", name: str = "mpvPlayer", max_bytes: int = 5 * 1024 * 1024, backup_count: int = 3) -> None:
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(log_level)
    ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s"))
    logger.addHandler(ch)

    # File handler
    log_file: Path = logs_dir() / f"{name}.log"
    fh = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
    fh.setLevel(log_level)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s"))
    logger.addHandler(fh)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
