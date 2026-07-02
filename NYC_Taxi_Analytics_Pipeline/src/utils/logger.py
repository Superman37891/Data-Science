import logging
from pathlib import Path

def setup_logger():
    LOG_DIR = Path.cwd() / "logs"
    LOG_DIR.mkdir(exist_ok=True)

    log_file = LOG_DIR / "pipeline.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(log_file, mode="a"),
            logging.StreamHandler()
        ],
        force=True  # 🔥 THIS IS CRITICAL (Python 3.8+)
    )