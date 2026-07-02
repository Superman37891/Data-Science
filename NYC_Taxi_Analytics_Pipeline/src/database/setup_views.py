import src.analytics.queries as queries
from pyathena import connect
import streamlit as st
from src.config import get_config

from dotenv import load_dotenv

import logging
logger = logging.getLogger(__name__)

load_dotenv()

def setup_database():
    connection = connect(
        s3_staging_dir=get_config('YELLOW_TAXI_S3_STAGING_DIR'),
        region_name=get_config('YELLOW_TAXI_AWS_REGION'),
        aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"],
        schema_name=get_config('YELLOW_TAXI_DATABASE')
    )
    cursor = connection.cursor()

    views_to_create = [
        queries.YELLOW_TAXI_ENRICHED_CREATE_QUERY,
        queries.KPI_OVERALL_MONTHLY_SUMMARY_QUERY
    ]

    print("Initializing Database Views...")
    for query in views_to_create:
        try:
            cursor.execute(query)
            logger.info("Successfully created view.")
        except Exception as e:
            print(f"Error creating view: {e}")

if __name__ == "__main__":
    setup_database()