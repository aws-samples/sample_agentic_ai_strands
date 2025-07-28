import boto3
from botocore.config import Config 
import os
from dotenv import load_dotenv
from urllib.parse import urlparse
from typing import Dict, Any
import json
import requests
from utils import generate_id_from_string
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

def invoke_local_runtime(session_id:str,payload:Dict[str,Any]):
    headers = {
        "X-Amzn-Trace-Id": "your-trace-id", 
        "Content-Type": "application/json",
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": "7a750a8c-11ab-447a-aec9-fe7b38402088222"
    }
    try:
        invoke_response = requests.post(
            "http://127.0.0.1:8080/invocations",
            headers=headers,
            data=json.dumps(payload),
            stream=True
        )
        if invoke_response.status_code == 200:
            return {"contentType":"text/event-stream","response":invoke_response}
        elif invoke_response.status_code >= 400:
            logger.info(f"Error Response ({invoke_response.status_code}):")
            error_data = invoke_response.json()
            logger.info(json.dumps(error_data, indent=2))
        else:
            logger.info(f"Unexpected status code: {invoke_response.status_code}")
            logger.info("Response text:")
            logger.info(invoke_response.text[:500])
    except Exception as e:
        logger.info(f"{str(e)}")
        
    
def invoke_agentcore_runtime(session_id:str,payload:Dict[str,Any],qualifier="DEFAULT",development=False):
    if development:
        return invoke_local_runtime(session_id=session_id,payload=payload)
    try:
        boto3_response = agentcore_client.invoke_agent_runtime(
                    agentRuntimeArn=invoke_agent_arn,
                    runtimeSessionId=session_id,
                    qualifier=qualifier,
                    payload=json.dumps(payload,ensure_ascii=False)
                )
        return boto3_response
    except Exception as e:
        # Check if it's the specific RuntimeClientError
        if ('RuntimeClientError' in str(type(e)) or 'RuntimeClientError' in str(e)) and 'InvokeAgentRuntime' in str(e):
            logger.warning(f"RuntimeClientError detected with session_id {session_id}: {e}")
            logger.info("Retrying with new session_id...")
            rand_str = str(uuid.uuid4())
            # Generate new session_id and retry
            new_session_id = generate_id_from_string(f"{rand_str}")
            logger.info(f"Retrying with new session_id: {new_session_id}")
            
            try:
                boto3_response = agentcore_client.invoke_agent_runtime(
                            agentRuntimeArn=invoke_agent_arn,
                            runtimeSessionId=new_session_id,
                            qualifier=qualifier,
                            payload=json.dumps(payload,ensure_ascii=False)
                        )
                logger.info("Retry successful")
                return boto3_response
            except Exception as retry_e:
                logger.error(f"Retry failed with session_id {new_session_id}: {retry_e}")
                raise retry_e
        else:
            # Re-raise if it's not the specific error we're handling
            raise e
