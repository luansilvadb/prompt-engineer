"""Logging estruturado com loguru — substitui print() por logger."""

import sys
from pathlib import Path
from loguru import logger

LOG_DIR = Path(__file__).parent.parent / "outputs" / "logs"


def setup_logging():
    """Configura loguru com formato estruturado e arquivo rotativo."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Remove handler padrão
    logger.remove()

    # Console: formato compacto para desenvolvimento
    logger.add(
        sys.stderr,
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        level="DEBUG",
        colorize=True,
    )

    # Arquivo rotativo: registro persistente com rotação diária, retenção 7 dias
    logger.add(
        LOG_DIR / "optimizer_{time:YYYY-MM-DD}.log",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
            "{level: <8} | "
            "{name}:{function}:{line} - "
            "{message}"
        ),
        level="DEBUG",
        rotation="00:00",  # Rotaciona à meia-noite
        retention="7 days",
        compression="zip",
        encoding="utf-8",
    )

    logger.info("Logging configurado — console + arquivo rotativo em {}", LOG_DIR)