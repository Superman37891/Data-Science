from dotenv import load_dotenv
import os

load_dotenv()

BUCKET_NAME = os.getenv("BUCKET_NAME")
S3_STAGING_DIR = os.getenv("S3_STAGING_DIR")
AWS_REGION = os.getenv("AWS_REGION")

DATASET = "yellow_taxi"
RAW_FOLDER = os.getenv("RAW_FOLDER", "raw_data/yellow_taxi")
PROCESSED_FOLDER = os.getenv("PROCESSED_FOLDER", "processed_data/yellow_taxi")
TABLE_NAME = "yellow_taxi_processed"
ENRICHED_TABLE_NAME = "yellow_taxi_enriched"
DATABASE = "taxi_data"
TLC_BASE_URL = 'https://d37ci6vzurychx.cloudfront.net/trip-data'

print(PROCESSED_FOLDER)