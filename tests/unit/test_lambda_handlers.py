import json
import importlib
from unittest.mock import patch


def test_chatbot_handler_success():
    chatbot_query = importlib.import_module("lambda_functions.chatbot_query")
    event = {"body": json.dumps({"query": "hi"})}
    with patch.object(chatbot_query, "embed_text", return_value=[1.0]), \
         patch.object(chatbot_query, "search_embeddings", return_value=["ctx"]), \
         patch.object(chatbot_query, "generate_answer", return_value="answer"):
        resp = chatbot_query.handler(event, None)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"]) == {"answer": "answer"}


def test_ingest_handler_processes_record(tmp_path):
    ingest_study_material = importlib.import_module("lambda_functions.ingest_study_material")
    event = {"Records": [{"s3": {"bucket": {"name": "b"}, "object": {"key": "k"}}}]}
    temp_dir = tmp_path
    with patch.object(ingest_study_material, "s3_client") as mock_s3, \
         patch.object(ingest_study_material, "extract_text", return_value="text"), \
         patch.object(ingest_study_material, "embed_text", return_value=[0.1]), \
         patch.object(ingest_study_material, "index_embedding") as mock_index, \
         patch.object(ingest_study_material.tempfile, "TemporaryDirectory") as mock_tmp:
        mock_tmp.return_value.__enter__.return_value = str(temp_dir)
        resp = ingest_study_material.handler(event, None)
    mock_s3.download_file.assert_called_once()
    mock_index.assert_called_once()
    assert resp["records"] == 1
