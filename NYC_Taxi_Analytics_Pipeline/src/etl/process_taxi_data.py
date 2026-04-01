import boto3
import pandas as pd
import numpy as np
from io import BytesIO
from collections import defaultdict
import src.config as config

from src.config import BUCKET_NAME
from src.utils.s3_file_exists import file_exists

s3 = boto3.client("s3")


RAW_PREFIX = f"{config.RAW_FOLDER}/"
PROCESSED_PREFIX = f"{config.PROCESSED_FOLDER}/"

MIN_EXPECTED_COLUMNS = \
    ["VendorID",
     "tpep_pickup_datetime",
     "tpep_dropoff_datetime",
     "passenger_count",
     "trip_distance",
     "PULocationID",
     "DOLocationID",
     "fare_amount",
     "extra",
     "payment_type",
]

def read_parquet_from_s3(key):
    obj = s3.get_object(Bucket=BUCKET_NAME, Key=key)
    return pd.read_parquet(BytesIO(obj["Body"].read()))


def write_parquet_to_s3(df, key):
    buffer = BytesIO()
    df.to_parquet(buffer, index=False)
    buffer.seek(0)

    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=key,
        Body=buffer.getvalue()
    )

def log_quality(key, issues):
    print(f"Quality Report for {key}")
    for k, v in issues.items():
        print(f"{k}: {v}")

def validate_schema(df):
    missing_columns = [col for col in MIN_EXPECTED_COLUMNS if col not in df.columns]
    if missing_columns:
        print(f"Missing columns: {missing_columns}")
        raise ValueError()
    else:
        print("Minimal schema requirements matched. Schema is valid.")

def delete_s3_prefix(bucket, prefix):
    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        if "Contents" in page:
            objects = [{"Key": obj["Key"]} for obj in page["Contents"]]

            s3.delete_objects(
                Bucket=bucket,
                Delete={"Objects": objects}
            )

def transform(df):
    """
    We only call this after the schema
    is validated in the main method
    """

    issues = {}

    df["tpep_pickup_datetime"] = pd.to_datetime(df["tpep_pickup_datetime"])
    df["tpep_dropoff_datetime"] = pd.to_datetime(df["tpep_dropoff_datetime"])

    ## null values
    issues["null_rows"] = df.isnull().any(axis=1).sum()
    df = df.dropna().copy()

    # duration
    df["trip_duration_min"] = (df["tpep_dropoff_datetime"] - df["tpep_pickup_datetime"]).dt.total_seconds() / 60.0
    issues["non_positive_duration"] = (df["trip_duration_min"] <= 0).sum()
    df = df[df["trip_duration_min"] > 0].copy()

    # distance
    issues["non_positive_distance"] = (df["trip_distance"] <= 0).sum()
    df = df[df["trip_distance"] > 0].copy()

    # payment type
    issues["bad_payment_type"] = (
            (df["payment_type"] < 0) |
            (df["payment_type"] > 6) |
            (df["payment_type"] % 1 != 0)
    ).sum()

    df["speed_mph"] = df["trip_distance"] / (df["trip_duration_min"] / 60.0)

    # handle infinities safely
    inf_count = (~np.isfinite(df["speed_mph"])).sum()
    issues["infinite_speed"] = inf_count
    df = df[np.isfinite(df["speed_mph"])].copy()

    # float casting
    df = df.astype({
    "trip_distance": "float64",
    "trip_duration_min": "float64",
    "speed_mph": "float64",
    "passenger_count": 'float64'
    })
    # Minimizes chances of these not being floats in production

    return df, issues


def get_s3_keys(prefix):
    paginator = s3.get_paginator("list_objects_v2")

    keys = []
    for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=prefix):
        keys.extend(obj["Key"] for obj in page.get("Contents", []))

    return keys

def main():

    detect_duplicates = True

    # =========================
    # 1. GET RAW FILES
    # =========================
    raw_keys = get_s3_keys(prefix=RAW_PREFIX)

    print(f"Found {len(raw_keys)} raw files")

    # =========================
    # 2. GET ALL PROCESSED KEYS ONCE (FAST)
    # =========================
    processed_keys = set(get_s3_keys(prefix=PROCESSED_PREFIX))
    processed_files = {
    key.split("/")[-1] for key in processed_keys
    }

    print(f"Found {len(processed_files)} processed files")

    # =========================
    # 3. PROCESS ONLY NEW FILES
    # =========================
    for key in raw_keys:

        file_name = key.split("/")[-1]
        if detect_duplicates and file_name in processed_files:
            print(f"Skipping because already processed: {file_name}")
            continue

        print(f"\nProcessing: {file_name}")

        # -------------------------
        # Load + transform
        # -------------------------
        df = read_parquet_from_s3(key)
        # Check if minimal schema requirements are present
        try:
            validate_schema(df)
        except ValueError as e:
            continue
        df, issues = transform(df)
        log_quality(key=key, issues=issues)

        # -------------------------
        # Partition extraction
        # -------------------------
        df["tpep_pickup_datetime"] = pd.to_datetime(df["tpep_pickup_datetime"])
        year = df["tpep_pickup_datetime"].dt.year.mode()[0]
        month = df["tpep_pickup_datetime"].dt.month.mode()[0]

        processed_key = (
            f"{PROCESSED_PREFIX}"
            f"year={year}/month={str(month).zfill(2)}/"
            f"{file_name}"
        )

        # -------------------------
        # Write output
        # -------------------------
        write_parquet_to_s3(df, processed_key)

        print(f"Saved: {processed_key}")

if __name__ == "__main__":
    main()