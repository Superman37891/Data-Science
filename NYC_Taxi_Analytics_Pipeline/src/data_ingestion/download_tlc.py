import json

import requests
from src.utils.s3_client import get_s3_client
from src.etl.process_taxi_data import check_if_file_exists_in_s3
import src.config as config
from datetime import datetime

import logging

logger = logging.getLogger(__name__)

s3 = get_s3_client()

def get_last_processed():
    try:
        obj = s3.get_object(Bucket=config.YELLOW_TAXI_BUCKET_NAME, Key="meta/last_processed.json")
        return json.loads(obj["Body"].read())
    except:
        return None

def save_last_processed(year, month, file_name):
    s3.put_object(
        Bucket=config.YELLOW_TAXI_BUCKET_NAME,
        Key="meta/last_processed.json",
        Body=json.dumps({
            "year": year,
            "month": month,
            "file_name": file_name
        })
    )

def get_latest_available():
    current_time = datetime.now()
    current_year = current_time.year
    current_month = current_time.month
    for year in range(current_year, 2023, -1):
        max_month = current_month if year == current_year else 12
        for month in range(max_month, 0, -1):
            filename = f"yellow_tripdata_{year}-{month:02d}.parquet"
            url = f"{config.TLC_BASE_URL}/{filename}"
            logger.info(f"TLC_BASE_URL = {config.TLC_BASE_URL!r}")
            response = requests.head(url)

            if response.status_code == 200:
                return year, month

    return -1, -1

def stream_download_to_s3(year: int, month: int) -> str:
    """
    Downloads TLC file and streams it directly into S3.
    Returns the S3 key.
    """

    filename = f"yellow_tripdata_{year}-{month:02d}.parquet"
    raw_s3_key = f"{config.YELLOW_TAXI_RAW_FOLDER}/year={year}/month={month:02d}/{filename}"
    if check_if_file_exists_in_s3(config.YELLOW_TAXI_BUCKET_NAME, raw_s3_key):
        logger.info("Raw file already exists.")
        return raw_s3_key

    url = f"{config.TLC_BASE_URL}/{filename}"

    logger.info(f"Streaming {filename} → S3")

    response = requests.get(url, stream=True)
    response.raise_for_status()

    buffer = bytearray()

    for chunk in response.iter_content(chunk_size=1024 * 1024):
        if chunk:
            buffer.extend(chunk)

    s3.put_object(
        Bucket=config.YELLOW_TAXI_BUCKET_NAME,
        Key=raw_s3_key,
        Body=bytes(buffer)
    )

    logger.info(f"Uploaded to s3://{config.YELLOW_TAXI_BUCKET_NAME}/{raw_s3_key}")

    return raw_s3_key