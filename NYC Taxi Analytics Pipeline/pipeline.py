from src.data_ingestion.download_tlc import stream_download_to_s3
from src.etl.process_taxi_data import process_file_from_s3_with_retry


def main(year: int, month: int):
    raw_key = stream_download_to_s3(year, month)
    process_file_from_s3_with_retry(raw_key)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)

    args = parser.parse_args()

    main(args.year, args.month)