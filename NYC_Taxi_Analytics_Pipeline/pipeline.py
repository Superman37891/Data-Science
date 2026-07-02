from src.data_ingestion.download_tlc import get_all_available, stream_download_to_s3, get_last_processed, save_last_processed
from src.etl.process_taxi_data import process_file_from_s3_with_retry
import logging
import os
import datetime as datetime
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(LOG_DIR, "pipeline.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-s] %(message)s",
)
logger = logging.getLogger(__name__)

def main():
    logger.info("Pipeline started")
    # skip already processed data
    last = get_last_processed()
    if last is None:
        last_year, last_month = 2024, '01'
    else:
        last_year, last_month = last

    available = get_all_available()
    if not available:
        logger.error("No datasets found from source. Aborting pipeline.")
        raise RuntimeError(
            "Dataset discovery failed: no available TLC files found. "
            "Check TLC_BASE_URL or network connectivity."
        )
    logger.info(f"Found {len(available)} available datasets")

    to_process = []
    for year, month in available:
        if not last:
            to_process.append((year, month))
        elif (year, month) > (last_year, last_month):
            to_process.append((year, month))

    if not to_process:
        logger.info("No new data to process (already up to date)")
        return

    logger.info("Backfill queue size: {len(to_process)}")

    for year, month in to_process:
        logger.info(f"Processing dataset: {year}-{month:02d}")

        try:
            # download → S3
            raw_key = stream_download_to_s3(year, month)

            # transform/load
            process_file_from_s3_with_retry(raw_key)

            # IMPORTANT: update checkpoint per file
            save_last_processed(year, month, raw_key)

            logger.info(f"Completed: {year}-{month:02d}")

        except Exception as e:
            logger.exception(f"Failed processing {year}-{month:02d}: {e}")
            # optional: stop pipeline OR continue
            raise

    logger.info("Pipeline finished successfully")

if __name__ == "__main__":
    main()