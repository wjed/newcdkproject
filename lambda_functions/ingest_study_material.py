import json
import os
import io
from datetime import datetime

import boto3
import fitz  # PyMuPDF
import docx
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth


def handler(event, context):
    """Process uploaded study material, generate embeddings and store them."""
    # Extract bucket and object key from the S3 event
    record = event['Records'][0]
    bucket = record['s3']['bucket']['name']
    key = record['s3']['object']['key']

    s3 = boto3.client('s3')
    resp = s3.get_object(Bucket=bucket, Key=key)
    body = resp['Body'].read()

    text = ''
    if key.lower().endswith('.pdf'):
        doc = fitz.open(stream=body, filetype='pdf')
        for page in doc:
            text += page.get_text()
    elif key.lower().endswith('.docx'):
        document = docx.Document(io.BytesIO(body))
        text = '\n'.join(p.text for p in document.paragraphs)
    else:
        print('Unsupported file type: %s', key)
        return {'statusCode': 400, 'body': 'Unsupported file type'}

    tokens = text.split()
    chunk_size = 500
    chunks = [' '.join(tokens[i:i + chunk_size]) for i in range(0, len(tokens), chunk_size)]

    bedrock = boto3.client('bedrock-runtime')
    region = os.environ.get('AWS_REGION', 'us-east-1')

    creds = boto3.Session().get_credentials()
    awsauth = AWS4Auth(creds.access_key, creds.secret_key, region, 'aoss', session_token=creds.token)
    opensearch = OpenSearch(
        hosts=[{'host': os.environ['OPENSEARCH_ENDPOINT'], 'port': 443}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
    )

    for idx, chunk in enumerate(chunks):
        resp = bedrock.invoke_model(
            modelId='amazon.titan-embed-text-v1',
            body=json.dumps({'inputText': chunk})
        )
        payload = json.loads(resp['body'].read())
        embedding = payload['embedding']

        document = {
            'id': f'{key}-{idx}',
            'text': chunk,
            'source': key,
            'timestamp': datetime.utcnow().isoformat(),
            'embedding': embedding,
        }

        opensearch.index(index='cert-embeddings', body=document, id=document['id'])

    return {'statusCode': 200, 'body': 'Processed'}
