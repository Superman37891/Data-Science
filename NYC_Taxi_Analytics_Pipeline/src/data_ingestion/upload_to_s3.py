import os
import re
from src.config import BUCKET_NAME, RAW_FOLDER
from src.utils.s3_client import get_s3_client
from src.utils.s3_file_exists import file_exists
from pathlib import Path

s3 = get_s3_client()

def extract_year_month(file_name):
    match = re.search(r"(\d{4})-(\d{2})", file_name)
    if not match:
        raise ValueError(f"Bad filename format: {file_name}")
    year, month = map(int, match.groups())
    return year, month

def upload_file(file_path):
    file_name = os.path.basename(file_path)
    year, month = extract_year_month(file_name)
    month = f"{month:02d}"
    year = str(year)
    s3_key = f"{RAW_FOLDER}/year={year}/month={month}/{file_name}"
    print("CHECKING:", s3_key)
    if file_exists(BUCKET_NAME, s3_key):
        print(f"Skipped (already exists): {file_name}\n")
        return
    print(f"File does not exist. Uploading: {file_name}")
    s3.upload_file(file_path, BUCKET_NAME, s3_key)
    print(f"Uploaded: {file_name} → s3://{BUCKET_NAME}/{s3_key}\n")

def main():
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    raw_folder = BASE_DIR / "data" / "raw"

    for file_name in sorted(os.listdir(raw_folder)):
        if not file_name.endswith(".parquet"):
            continue

        file_path = os.path.join(raw_folder, file_name)

        try:
            upload_file(file_path)
        except Exception as e:
            print(f"Failed {file_name}: {e}")


if __name__ == "__main__":
    main()