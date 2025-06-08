import os
import boto3

# Ensure boto3 clients can be created without raising NoRegionError
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.setdefault("AWS_SESSION_TOKEN", "test")

boto3.setup_default_session()
