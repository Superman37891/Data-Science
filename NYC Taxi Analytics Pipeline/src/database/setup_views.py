import src.analytics.queries as queries
from pyathena import connect
import streamlit as st
import src.config as config


from dotenv import load_dotenv
import os

load_dotenv()

def setup_database():
    connection = connect(
        s3_staging_dir=config.S3_STAGING_DIR,
        region_name=config.AWS_REGION,
        aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"],
        schema_name=config.DATABASE
    )
    cursor = connection.cursor()

    views_to_create = [
        queries.YELLOW_TAXI_ENRICHED_QUERY,
        queries.KPI_MONTHLY_REVENUE_QUERY,
        queries.KPI_MONTHLY_TRIPS_QUERY,
        queries.KPI_CUMULATIVE_REVENUE_QUERY,
        queries.KPI_MONTHLY_AVG_FARE_QUERY,
        queries.KPI_MONTHLY_AVG_SPEED_QUERY,
        queries.KPI_MONTHLY_SUMMARY_QUERY
    ]

    print("Initializing Database Views...")
    for query in views_to_create:
        try:
            cursor.execute(query)
            print("Successfully created view.")
        except Exception as e:
            print(f"Error creating view: {e}")

if __name__ == "__main__":
    setup_database()