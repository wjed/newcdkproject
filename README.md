# AI Certification Study Assistant

This project deploys AWS resources for a chatbot that indexes study material from an S3 bucket and serves answers through an API Gateway endpoint. Embeddings are generated using Amazon Bedrock and stored in an OpenSearch Serverless collection.

## Setup

1. Create and activate a Python virtual environment.
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
2. Install the dependencies for the CDK app and tests.
   ```bash
   pip install -r requirements.txt -r requirements-dev.txt
   ```
3. Build the Lambda layer containing third‑party packages. Dependencies are
   listed in `lambda_functions/requirements.txt`.
   ```bash
   ./build_layer.sh
   ```
4. Synthesize the CloudFormation template and deploy.
   ```bash
   cdk synth
   cdk deploy
   ```

After deployment, note the `ChatbotApiUrl` output. You can test the chatbot with:

```bash
curl -X POST <ChatbotApiUrl>ask \
  -H "Content-Type: application/json" \
  -d '{"query": "What is IAM?"}'
```
