import importlib


def test_sanitize_id():
    module = importlib.import_module("lambda_functions.ingest_study_material")
    assert module.sanitize_id("folder/file.pdf") == "folder_file.pdf"
