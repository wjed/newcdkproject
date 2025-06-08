import json
import os
import tempfile

import boto3
import PyPDF2
from docx import Document
from requests_aws4auth import AWS4Auth
import requests

s3_client = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime")
region = boto3.Session().region_name
credentials = boto3.Session().get_credentials()
auth = AWS4Auth(credentials.access_key, credentials.secret_key, region, "aoss", session_token=credentials.token)

OPENSEARCH_ENDPOINT = os.environ.get("OPENSEARCH_ENDPOINT")
INDEX_NAME = "cert-embeddings"


def extract_text(file_path: str) -> str:
    if file_path.endswith(".pdf"):
        text = []
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text.append(page.extract_text() or "")
        return "\n".join(text)
    elif file_path.endswith(".docx"):
        doc = Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs)
    else:
        raise ValueError("Unsupported file type")


def embed_text(text: str) -> list:
    body = json.dumps({"inputText": text})
    response = bedrock.invoke_model(modelId="amazon.titan-embed-text-v1", body=body)
    payload = json.loads(response["body"].read())
    return payload.get("embedding")


def sanitize_id(id_: str) -> str:
    """Make an S3 object key safe for use as a document ID."""
    return id_.replace("/", "_")


def index_embedding(id_: str, embedding: list, text: str) -> None:
    """Store the extracted text and its embedding in OpenSearch."""
    safe_id = sanitize_id(id_)
    url = f"https://{OPENSEARCH_ENDPOINT}/{INDEX_NAME}/_doc/{safe_id}"
    headers = {"Content-Type": "application/json"}
    data = json.dumps({"vector": embedding, "text": text})
    requests.put(url, auth=auth, headers=headers, data=data)


def handler(event, context):
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = record["s3"]["object"]["key"]
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = os.path.join(tmpdir, os.path.basename(key))
            s3_client.download_file(bucket, key, tmp_path)
            text = extract_text(tmp_path)
            embedding = embed_text(text)
            index_embedding(key, embedding, text)
    return {"status": "processed", "records": len(event.get("Records", []))}
