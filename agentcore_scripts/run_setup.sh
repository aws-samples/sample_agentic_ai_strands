#!/bin/bash
set -e

echo "============run ./setup_role.py =========="
uv run ./setup_role.py > iam-role.txt
echo "please find detail info in ./iam-role.txt"


echo "============run ./setup_id.py =========="
uv run ./setup_id.py > identity.txt
echo "please find detail info in .env_cognito"


echo "============run ./setup_memtory.py =========="
uv run ./setup_memory.py > memory.txt
echo "please find detail info in memory.txt"