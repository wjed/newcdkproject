import json
import os

import boto3
import requests
from requests_aws4auth import AWS4Auth

bedrock = boto3.client("bedrock-runtime")
region = boto3.Session().region_name
credentials = boto3.Session().get_credentials()
auth = AWS4Auth(credentials.access_key, credentials.secret_key, region, "aoss", session_token=credentials.token)

OPENSEARCH_ENDPOINT = os.environ.get("OPENSEARCH_ENDPOINT")
INDEX_NAME = "cert-embeddings"


def embed_text(text: str) -> list:
    body = json.dumps({"inputText": text})
    response = bedrock.invoke_model(modelId="amazon.titan-embed-text-v1", body=body)
    payload = json.loads(response["body"].read())
    return payload.get("embedding")


def search_embeddings(vector: list) -> list:
    url = f"https://{OPENSEARCH_ENDPOINT}/{INDEX_NAME}/_search"
    headers = {"Content-Type": "application/json"}
    query = {
        "size": 5,
        "query": {"knn": {"vector": {"vector": vector, "k": 5}}},
        "_source": ["text"],
    }
    r = requests.get(url, auth=auth, headers=headers, data=json.dumps(query))
    r.raise_for_status()
    hits = r.json().get("hits", {}).get("hits", [])
    return [hit.get("_source", {}).get("text", "") for hit in hits]


def generate_answer(question: str, context: str) -> str:
    prompt = f"\n\n{context}\n\nQuestion: {question}\nAnswer:"
    body = json.dumps({"prompt": prompt, "max_tokens_to_sample": 200})
    response = bedrock.invoke_model(modelId="anthropic.claude-v2", body=body)
    payload = json.loads(response["body"].read())
    return payload.get("completion", "")


def handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return {"statusCode": 400, "body": json.dumps({"error": "Invalid JSON"})}

    query = body.get("query")
    if not query:
        return {"statusCode": 400, "body": json.dumps({"error": "Missing query"})}

    embedding = embed_text(query)
    chunks = search_embeddings(embedding)
    context_str = "\n\n".join(chunks)
    answer = generate_answer(query, context_str)

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"answer": answer}),
    }
