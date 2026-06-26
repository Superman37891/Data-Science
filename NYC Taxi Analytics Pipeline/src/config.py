from dotenv import load_dotenv
import os

load_dotenv()

BUCKET_NAME = os.getenv("BUCKET_NAME")
S3_STAGING_DIR = os.getenv("S3_STAGING_DIR")
AWS_REGION = os.getenv("AWS_REGION")

DATASET = "yellow_taxi"
RAW_FOLDER = f"raw_data/{DATASET}"
PROCESSED_FOLDER = f"processed_data/{DATASET}"
TABLE_NAME = "yellow_taxi_processed"
ENRICHED_TABLE_NAME = "yellow_taxi_enriched"
DATABASE = "taxi_data"

print(RAW_FOLDER)
print(PROCESSED_FOLDER)
print(BUCKET_NAME)