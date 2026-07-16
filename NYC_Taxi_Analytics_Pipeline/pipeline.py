from src.data_ingestion.download_tlc import get_all_available, stream_download_to_s3, get_last_processed, save_last_processed
from src.etl.process_taxi_data import process_file_from_s3_with_retry
import src.utils.logger as logger
from src.config import START_YEAR, END_YEAR
import logging

logger.setup_logger()
logger_object = logging.getLogger(__name__)

def main():
    logger_object.info("Pipeline started")
    # skip already processed data
    last = get_last_processed()
    if last is None:
        last_year, last_month = START_YEAR, 1
    else:
        last_year = int(last["year"])
        last_month = int(last["month"])

    available = get_all_available()
    if not available:
        logger_object.error("No datasets found from source. Aborting pipeline.")
        raise RuntimeError(
            "Dataset discovery failed: no available TLC files found. "
            "Check TLC_BASE_URL or network connectivity."
        )
    logger_object.info(f"Found {len(available)} available datasets")

    to_process = []
    for year, month in available:
        if (year, month) > (last_year, last_month):
            to_process.append((year, month))

    if not to_process:
        logger_object.info("No new data to process (already up to date)")
        return

    logger_object.info(f"Backfill queue size: {len(to_process)}")

    for year, month in to_process:
        logger_object.info(f"Processing dataset: {year}-{month:02d}")

        try:
            # download → S3
            raw_key = stream_download_to_s3(year, month)

            # transform/load
            process_file_from_s3_with_retry(raw_key)

            # IMPORTANT: update checkpoint per file
            save_last_processed(year, month, raw_key)

            logger_object.info(f"Completed: {year}-{month:02d}")

        except Exception as e:
            logger_object.exception(f"Failed processing {year}-{month:02d}: {e}")
            # optional: stop pipeline OR continue
            raise

    logger_object.info("Pipeline finished successfully")

if __name__ == "__main__":
    main()