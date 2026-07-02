import boto3
import src.config

athena = boto3.client("athena")

DATABASE = src.config.YELLOW_TAXI_DATABASE

OUTPUT_LOCATION = "s3://nyc-taxi-analytics-pipeline-37891/athena-results/"

QUERY = """
SELECT year, month, COUNT(*) AS total_trips
FROM yellow_taxi_processed
GROUP BY year, month
ORDER BY year, month;
"""

def lambda_handler(event, context):
    record = event["Records"][0]
    key = record["s3"]["object"]["key"]

    print("New file:", key)

    # extract year/month from path
    import re
    match = re.search(r"year=(\d+)/month=(\d+)", key)

    if match:
        year, month = match.groups()

        query = f"""
        SELECT COUNT(*) 
        FROM yellow_taxi_processed
        WHERE year = {year} AND month = {month};
        """

        athena.start_query_execution(
            QueryString=query,
            QueryExecutionContext={"Database": DATABASE},
            ResultConfiguration={"OutputLocation": OUTPUT_LOCATION}
        )