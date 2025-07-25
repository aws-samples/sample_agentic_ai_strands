#!/bin/bash
set -e

echo "============run ./setup_id.py =========="
uv run ./setup_id.py > identity.txt

echo "please find detail info in ./identity.txt"
