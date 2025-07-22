#!/bin/bash
echo "============run ./setup_role.py =========="
uv run ./setup_role.py > iam-role.txt

echo "============run ./setup_id.py =========="
uv run ./setup_id.py > identity.txt