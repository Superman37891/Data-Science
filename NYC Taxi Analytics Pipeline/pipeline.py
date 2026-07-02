from src.data_ingestion.download_tlc import get_latest_available, stream_download_to_s3
from src.etl.process_taxi_data import process_file_from_s3_with_retry

import logging

logger = logging.getLogger(__name__)

def main():
    year, month = get_latest_available()
    # skip already processed data

    if year == -1:
        logger.warning("No data available for this year and month")
        raise RuntimeError("No available TLC dataset found\n")

    raw_key = stream_download_to_s3(year, month)
    process_file_from_s3_with_retry(raw_key)

if __name__ == "__main__":
    main()