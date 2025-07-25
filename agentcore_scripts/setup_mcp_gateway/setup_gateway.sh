#!/bin/bash
set -e
# Check if required arguments are provided
if [ "$#" -lt 2 ]; then
    echo "Usage: $0 <api-key> <bucket-name>"
    echo "Example: $0 my-api-key my-bucket-name"
    exit 1
fi
# Get arguments from command line
API_KEY="$1"
BUCKET_NAME="$2"
# Run the Python script with the provided arguments
uv run gateway_deploy.py --my-api-key "$API_KEY" --bucket-name "$BUCKET_NAME"
