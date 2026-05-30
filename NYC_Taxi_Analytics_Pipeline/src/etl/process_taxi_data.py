import boto3
import pandas as pd
import numpy as np
from io import BytesIO
from collections import defaultdict
import src.config as config

import pyarrow as pa
import pyarrow.parquet as pq

from src.config import BUCKET_NAME
from src.utils.s3_file_exists import file_exists

s3 = boto3.client("s3")


RAW_PREFIX = f"{config.RAW_FOLDER}/"
PROCESSED_PREFIX = f"{config.PROCESSED_FOLDER}/"

MIN_EXPECTED_COLUMNS = [
    "VendorID",
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "passenger_count",
    "trip_distance",
    "PULocationID",
    "DOLocationID",
    "payment_type",
    "fare_amount"
]

REQUIRED_COLUMNS = [
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "trip_distance",
    "payment_type",
    "fare_amount"
]

ENGINEERED_COLUMNS = [
    "trip_duration_min",
    "speed_mph",
    "valid_payment"
]

def read_parquet_from_s3(key):
    obj = s3.get_object(Bucket=BUCKET_NAME, Key=key)
    return pd.read_parquet(BytesIO(obj["Body"].read()))


def write_parquet_to_s3(df, key):

    table = pa.Table.from_pandas(df)

    buffer = BytesIO()
    pq.write_table(table, buffer)
    #buffer.seek(0)
    s3.put_object(
        Bucket = BUCKET_NAME,
        Key=key,
        Body=buffer.getvalue()
    )

def log_quality(key, df):
    print(f"\nQUALITY REPORT: {key}")

    for _, row in df.iterrows():

        print(f"\nStage: {row['stage']}")
        print("-" * 40)

        for col, value in row.items():

            if col == "stage":
                continue

            print(f"{col:<30}: {value}")

def delete_s3_prefix(bucket, prefix):
    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        if "Contents" in page:
            objects = [{"Key": obj["Key"]} for obj in page["Contents"]]

            s3.delete_objects(
                Bucket=bucket,
                Delete={"Objects": objects}
            )


def validate_schema(df):
    missing_columns = [col for col in MIN_EXPECTED_COLUMNS if col not in df.columns]
    if missing_columns:
        print(f"Missing columns: {missing_columns}")
        raise ValueError()
    else:
        print("Minimal schema requirements matched. Schema is valid.")

def add_features(df):
    df = df.copy()
    df["tpep_pickup_datetime"] = pd.to_datetime(df["tpep_pickup_datetime"], errors="coerce")
    df["tpep_dropoff_datetime"] = pd.to_datetime(df["tpep_dropoff_datetime"], errors="coerce")
    df["trip_duration_min"] = (df["tpep_dropoff_datetime"] - df["tpep_pickup_datetime"]).dt.total_seconds() / 60.0
    df["speed_mph"] = np.where(df["trip_duration_min"] > 0,
                               df["trip_distance"] / (df["trip_duration_min"] / 60.0),
                               np.nan
                               )
    df["valid_payment"] = (
            (df["payment_type"].notna()) &
            (df["payment_type"].between(1, 5)) &
            (df["payment_type"] % 1 == 0)
    )

    return df


def remove_bad_rows(df, expected_year, expected_month):
    """
    We only call this after the schema
    is validated in the main method
    """


    df = df.dropna(subset=REQUIRED_COLUMNS)

    # duration
    df = df.loc[df["trip_duration_min"] > 0]

    # distance
    df = df.loc[df["trip_distance"] > 0]

    # payment type
    df = df.loc[df["valid_payment"]]

    # float casting
    df = df.astype({
    "trip_distance": "float64",
    "trip_duration_min": "float64",
    "speed_mph": "float64",
    "passenger_count": 'float64'
    })

    if not pd.api.types.is_datetime64_any_dtype(df["tpep_pickup_datetime"]):
        raise ValueError("Datetime column not parsed. Run add_features first")

    df = df.loc[
        (df["tpep_pickup_datetime"].dt.year == expected_year) &
        (df["tpep_pickup_datetime"].dt.month == expected_month)
        ]

    return df

def get_issues(df, expected_year, expected_month):
    """
    Note: Run this after add_features
    """

    issues = {}
    '''
    a guard in case someone calls get_issues without
    add_features first
    '''

    if "tpep_pickup_datetime" in df.columns:
        dt = df["tpep_pickup_datetime"]
    else:
        raise ValueError("Missing pickup datetime column. Run add_features first")

    if "trip_duration_min" not in df.columns or "speed_mph" not in df.columns:
        raise ValueError("Engineered features missing. Run add_features first.")

    # Our validate_schema function checks for missing columns
    original_cols_df = df.drop(columns=ENGINEERED_COLUMNS, errors="ignore")
    issues["null_rows"] = int(original_cols_df.isnull().any(axis=1).sum())
    issues["null_cells"] = int(original_cols_df.isnull().sum().sum())
    null_percent = original_cols_df.isnull().mean() * 100
    issues["cols_null_percentages"] = null_percent[null_percent > 0].sort_values(ascending=False).to_dict()

    issues["non_positive_distance"] = (df["trip_distance"] <= 0).sum()

    non_positive_trip_durations = int((df["trip_duration_min"] <= 0).sum())
    issues["non_positive_duration"] = non_positive_trip_durations

    issues["bad_payment_type"] = (~df["valid_payment"]).sum()
    issues["infinite_speed_count"] = (~np.isfinite(df["speed_mph"])).sum()

    wrong_year = int((dt.dt.year.fillna(-1) != expected_year).sum())
    wrong_month = int((dt.dt.month.fillna(-1) != expected_month).sum())

    issues["wrong_year"] = wrong_year
    issues["wrong_month"] = wrong_month
    return issues

def get_s3_keys(prefix):
    paginator = s3.get_paginator("list_objects_v2")

    keys = []
    for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=prefix):
        keys.extend(obj["Key"] for obj in page.get("Contents", []))

    return keys

def extract_partition_from_key(key):
    parts = key.split("/")

    year_part = [p for p in parts if p.startswith("year=")][0]
    month_part = [p for p in parts if p.startswith("month=")][0]

    expected_year = int(year_part.split("=")[1])
    expected_month = int(month_part.split("=")[1])

    return expected_year, expected_month

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

        expected_year, expected_month = extract_partition_from_key(key)

        df_raw = read_parquet_from_s3(key)
        try:
            validate_schema(df_raw)
        except ValueError:
            continue
        raw_df_len = len(df_raw)

        df_engineered = add_features(df_raw)

        pre_cleaned_issues = get_issues(df_engineered, expected_year, expected_month)
        # Check if minimal schema requirements are present


        # -------------------------
        # Partition extraction
        # -------------------------

        df_clean = remove_bad_rows(df_engineered, expected_year, expected_month)
        post_cleaned_issues = get_issues(df_clean, expected_year, expected_month)
        cleaned_df_len = len(df_clean)

        df_clean = df_clean.drop(columns=["valid_payment"])# compute once

        processed_key = (
            f"{PROCESSED_PREFIX}"
            f"year={expected_year}/month={str(expected_month).zfill(2)}/"
            f"{key}"
        )

        row_loss_percent = ((1-cleaned_df_len/raw_df_len)*100 if raw_df_len > 0 else 0)
        issues_df = pd.DataFrame([
            {"stage": "pre-cleaned", **pre_cleaned_issues},
            {"stage": "cleaned", **post_cleaned_issues}
            ])
        summary_df = pd.DataFrame([
            {
                "stage": "summary",
                "raw_rows": raw_df_len,
                "cleaned_rows": cleaned_df_len,
                "rows_lost": raw_df_len - cleaned_df_len,
                "loss_percent": row_loss_percent
            }
        ])

        log_quality(key=key, df=issues_df)
        log_quality(key=key, df=summary_df)
        # The "QUALITY REPORT: {key}" gets printed twice due to
        # calling log_quality twice, which is not intended

        # -------------------------
        # Write output
        # -------------------------
        write_parquet_to_s3(df_clean, processed_key)

        print(f"Saved: {processed_key}")

if __name__ == "__main__":
    main()