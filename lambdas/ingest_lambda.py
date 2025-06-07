import json

def handler(event, context):
    print("Received event: " + json.dumps(event))
    return {"status": "ingested"}
