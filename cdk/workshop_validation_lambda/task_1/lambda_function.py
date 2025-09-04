import json
import boto3
import base64
import logging
import re
from typing import List, Dict, Any,Optional

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def extract_agent_info_from_arn(agent_runtime_arn: str) -> Dict[str, str]:
    """
    Extract agent runtime ID from the ARN.
    
    ARN format: arn:aws:bedrock-agentcore:region:account:runtime/agent_runtime_id
    """
    # Extract agent runtime ID from ARN
    pattern = r'arn:.*:bedrock-agentcore:.*:.*:runtime/(.+)'
    match = re.match(pattern, agent_runtime_arn)
    
    if not match:
        raise ValueError(f"Invalid agent runtime ARN format: {agent_runtime_arn}")
    
    agent_runtime_id = match.group(1)
    
    return {
        'agent_runtime_id': agent_runtime_id
    }

def check_agent_runtime_status(agent_runtime_arn: str, 
                             aws_region: str = None,
                             aws_profile: str = None) -> Dict[str, Any]:
    """
    Check the status of an Amazon Bedrock AgentCore Runtime.
    
    Args:
        agent_runtime_arn (str): The ARN of the agent runtime
        aws_region (str, optional): AWS region. If not provided, uses default region
        aws_profile (str, optional): AWS profile to use. If not provided, uses default profile
    
    Returns:
        Dict containing status information and full response
    """
    try:
        # Extract agent runtime ID from ARN
        agent_info = extract_agent_info_from_arn(agent_runtime_arn)
        agent_runtime_id = agent_info['agent_runtime_id']
        
        # Create boto3 session and client
        session = boto3.Session(profile_name=aws_profile) if aws_profile else boto3.Session()
        client = session.client('bedrock-agentcore-control', region_name=aws_region)
        
        # Call GetAgentRuntime API
        response = client.get_agent_runtime(
            agentRuntimeId=agent_runtime_id
        )
        
        status = response.get('status', 'UNKNOWN')
        is_ready = status == 'READY'
        
        return is_ready
    except Exception as e:
        # Handle all exceptions including ResourceNotFoundException and AccessDeniedException
        logger.error(f"Error checking agent runtime status: {str(e)}")
        return False
    
# check if the agentcore_runtime is deployed
def lambda_handler(event, context):
    """
    This function is the entry point for the Lambda function. It checks if the agentcore_runtime is deployed and if the user input matches the expected value.

    Args:
        event (dict): The event data passed to the Lambda function.
        context (object): The context object passed to the Lambda function.

    Returns:
        dict: A dictionary containing the following keys:
            - completed (bool): Whether the task is completed or not.
            - message (str): A message indicating the progress or next steps.
            - progressPercent (int): The progress percentage (if applicable).
            - metadata (dict): Additional metadata (if applicable).
    """
    taskguid = event.get("TASKGUID", None)
    runtime_arn = event.get("AGENTCORE_RUNTIME_ARN", None)

    result = check_agent_runtime_status(runtime_arn)
    
    success_message = "Error"
    if result:
        success_message = "AgentCore runtime agent is available and running."

    logging.info(f"Task GUID: {taskguid}")
    logging.info(f"success_message: {success_message}")

    combined_message = f"{taskguid}-{success_message}"

    # Encrypt the message using base64 encoding
    encrypted_message = base64.b64encode(combined_message.encode('utf-8')).decode('utf-8')

    return {
        "encrypted_message": encrypted_message
    }