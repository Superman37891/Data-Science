from src.data_ingestion.download_tlc import get_latest_available, stream_download_to_s3
from src.etl.process_taxi_data import process_file_from_s3_with_retry

import logging
import os
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(LOG_DIR, "pipeline.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-s] %(message)s",
)
logger = logging.getLogger(__name__)

import os
print("TLC_BASE_URL =", os.getenv("TLC_BASE_URL"))

def main():
    logger.info("Pipeline started")
    year, month = get_latest_available()
    # skip already processed data

    if year == -1:
        logger.warning("No data available for this year and month")
        raise RuntimeError("No available TLC dataset found\n")

    raw_key = stream_download_to_s3(year, month)
    process_file_from_s3_with_retry(raw_key)
    logger.info(f"Pipeline finished for file {raw_key}")

if __name__ == "__main__":
    main()