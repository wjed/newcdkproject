#!/bin/bash
set -euo pipefail
mkdir -p lambda_layer/python
pip install -r lambda_functions/requirements.txt -t lambda_layer/python
