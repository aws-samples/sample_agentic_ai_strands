import boto3
from botocore.config import Config 
import os
from dotenv import load_dotenv
from urllib.parse import urlparse
from typing import Dict, Any
import json
from botocore.exceptions import ClientError
import asyncio
import uuid
import logging
load_dotenv()

# Initialize logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
)
logger = logging.getLogger(__name__)


agentcore_client = boto3.client(
        'bedrock-agentcore',
        config = Config(
                region_name=os.environ.get("AGENTCORE_REGION",'us-west-2'),
                read_timeout=900,
                connect_timeout=900,
                retries=dict(max_attempts=6, mode="adaptive"),
                ),
    )

invoke_agent_arn = os.environ.get("AGENTCORE_RUNTIME_ARN")

def invoke_agentcore_runtime(session_id:str,payload:Dict[str,Any],qualifier="DEFAULT"):

    boto3_response = agentcore_client.invoke_agent_runtime(
                agentRuntimeArn=invoke_agent_arn,
                runtimeSessionId=session_id,
                qualifier=qualifier,
                payload=json.dumps(payload,ensure_ascii=False)
            )  
    return boto3_response
