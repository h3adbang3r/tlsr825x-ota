from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path


def configure_logging(verbose: bool, log_dir: Path = Path("logs")) -> tuple[logging.Logger, Path]:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"tlsr825x-ota_{datetime.now():%Y%m%d_%H%M%S}.log"
    logger = logging.getLogger("tlsr825x_ota")
    logger.handlers.clear()
    logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    stream_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(stream_handler)
    return logger, log_path
