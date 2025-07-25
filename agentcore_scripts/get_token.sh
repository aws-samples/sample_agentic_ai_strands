#!/bin/bash
set -e

if [ $# -eq 0 ]; then
    echo "Usage: $0 <client_id>"
    exit 1
fi
ID=$1
echo "============run ./get_token.py =========="
uv run ./get_token.py --client "${ID}"