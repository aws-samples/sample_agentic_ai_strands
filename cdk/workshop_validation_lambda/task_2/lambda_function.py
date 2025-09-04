import json
import boto3
import base64
import logging
from typing import List, Dict, Any

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
TGT_STACK_NAME= 'StrandsAgentsEcsFargateStack'

def fetch_cf_status() -> bool:
    """
    Function to check all CloudFormation stacks in the current account/region
    for outputs containing 'TASKSGUID'
    """
    try:
        # Initialize CloudFormation client
        cf_client = boto3.client('cloudformation')
        
        # Get all stacks in the account/region
        stacks_with_tasksguid = []
        paginator = cf_client.get_paginator('list_stacks')
        stack_found = False
        # Iterate through all stacks (including deleted ones if needed)
        for page in paginator.paginate(
            StackStatusFilter=[
                'CREATE_COMPLETE',
                'UPDATE_COMPLETE'
            ]
        ):  
            for stack in page['StackSummaries']:
                if stack_found:
                    break
                if stack['StackName'] == TGT_STACK_NAME:
                    stack_found = True
                    
        
        logger.info(f"Scan completed. Found {TGT_STACK_NAME}.")
        return stack_found
        
    except Exception as e:
        logger.error(f"Error in lambda execution: {str(e)}")
        return False

def lambda_handler(event, context):

    # Available data provided in the event
    taskguid = event.get("TASKGUID", None)
    
    logging.info(f"Task GUID: {taskguid}")
    
    result = fetch_cf_status()
    
    success_message = "Error"
    if result:
        success_message = "ECS cluster is available and running."

    logging.info(f"success_message: {success_message}")

    combined_message = f"{taskguid}-{success_message}"

    # Encrypt the message using base64 encoding
    encrypted_message = base64.b64encode(combined_message.encode('utf-8')).decode('utf-8')

    return {
        "encrypted_message": encrypted_message,
        "message": f"{success_message}"

    }