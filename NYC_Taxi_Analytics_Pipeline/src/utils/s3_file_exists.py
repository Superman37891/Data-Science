import boto3
from botocore.exceptions import ClientError

s3 = boto3.client("s3")

def file_exists(bucket, key):
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError:
        return False