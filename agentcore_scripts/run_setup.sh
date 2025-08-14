#!/bin/bash
set -e

echo "============setup ecr repo================"
uv run ./setup_ecr.py

echo "============run ./setup_role.py =========="
uv run ./setup_role.py 


echo "============run ./setup_id.py =========="
uv run ./setup_id.py 

echo "============run ./setup_memory.py =========="
uv run ./setup_memory.py 

echo "please find detail info in .env_setup"

echo "============run copy env and yaml =========="
cp ../env.example ../.env
cp ../bedrock_agentcore_template.yaml .bedrock_agentcore.yaml

echo "============run ./update_env.py =========="
uv run ./update_env.py 