import requests
from src.utils.s3_client import get_s3_client

from src.etl.process_taxi_data import check_if_file_exists_in_s3
from src.config import TLC_BASE_URL, BUCKET_NAME, RAW_FOLDER

s3 = get_s3_client()

def stream_download_to_s3(year: int, month: int) -> str:
    """
    Downloads TLC file and streams it directly into S3.
    Returns the S3 key.
    """

    filename = f"yellow_tripdata_{year}-{month:02d}.parquet"
    raw_s3_key = f"{RAW_FOLDER}/year={year}/month={month:02d}/{filename}"
    if check_if_file_exists_in_s3(BUCKET_NAME, raw_s3_key):
        print("Raw file already exists.")
        return raw_s3_key

    url = f"{TLC_BASE_URL}/{filename}"

    print(f"Streaming {filename} → S3")

    response = requests.get(url, stream=True)
    response.raise_for_status()

    buffer = bytearray()

    for chunk in response.iter_content(chunk_size=1024 * 1024):
        if chunk:
            buffer.extend(chunk)

    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=raw_s3_key,
        Body=bytes(buffer)
    )

    print(f"Uploaded to s3://{BUCKET_NAME}/{raw_s3_key}")

    return raw_s3_key