import requests
import urllib.parse
import json
import os
import sys
sys.path.append('../')
from agentcore_scripts.utils_bak import get_user_token
# Enable verbose logging for requests
import logging
logging.basicConfig(level=logging.INFO)
logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)
from boto3.session import Session
import uuid
boto_session = Session()

REGION_NAME = boto_session.region_name
print(REGION_NAME)

BEDROCK_AGENT_CORE_ENDPOINT_URL="https://bedrock-agentcore.us-west-2.amazonaws.com"

# Update the agent ARN. You can get the agent arn from the .bedrock_agentcore.yaml file
invoke_agent_arn = "arn:aws:bedrock-agentcore:us-west-2:434444145045:runtime/agent_runtime-iBIWWKHPC1"
# URL encode the agent ARN
escaped_agent_arn = urllib.parse.quote(invoke_agent_arn, safe='')
print(escaped_agent_arn)
# Construct the URL
url = f"{BEDROCK_AGENT_CORE_ENDPOINT_URL}/runtimes/{escaped_agent_arn}/invocations?qualifier=DEFAULT"
print(f"URL: {url}")

def generate_id_from_string(input_string):
    # 基于输入字符串生成UUID5
    namespace = uuid.NAMESPACE_DNS  # 使用预定义的命名空间
    unique_id = uuid.uuid5(namespace, input_string)
    # 转为字符串并确保长度为33
    return str(unique_id).replace('-', '')[:33].ljust(33, '0')

import json
import boto3

agentcore_client = boto3.client(
        'bedrock-agentcore',
        region_name='us-west-2'
    )

def remove_mcp_test_boto3():
    payload = {
        "user_id":"001",
        "request_type":"deletemcpserver",
        "data" : {"server_id":"amap"}
    }

    boto3_response = agentcore_client.invoke_agent_runtime(
        agentRuntimeArn=invoke_agent_arn,
        qualifier="DEFAULT",
        payload=json.dumps(payload,ensure_ascii=False)
    )
    if "text/event-stream" in boto3_response.get("contentType", ""):
        content = []
        for line in boto3_response["response"].iter_lines(chunk_size=1):
            if line:
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    line = line[6:]
                    print(line)
                    content.append(line)
        print("\n".join(content))
    else:
        try:
            events = []
            for event in boto3_response.get("response", []):
                events.append(event)
        except Exception as e:
            events = [f"Error reading EventStream: {e}"]
        print(json.loads(events[0].decode("utf-8")))
    
def add_mcp_test_boto3():
    payload = {
        "request_type":"addmcpserver",
        "user_id":"001",
        "data" :{"server_id":"amap","server_desc":"","command":"npx","config_json":{
		    "url": "https://mcp.amap.com/sse?key=dca4882fb0aef3c044e89b55304a0e0e"
		}}
    }


    boto3_response = agentcore_client.invoke_agent_runtime(
        agentRuntimeArn=invoke_agent_arn,
        qualifier="DEFAULT",
        payload=json.dumps(payload)
    )
    if "text/event-stream" in boto3_response.get("contentType", ""):
        content = []
        for line in boto3_response["response"].iter_lines(chunk_size=1):
            if line:
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    line = line[6:]
                    print(line)
                    content.append(line)
        print("\n".join(content))
    else:
        try:
            events = []
            for event in boto3_response.get("response", []):
                events.append(event)
        except Exception as e:
            events = [f"Error reading EventStream: {e}"]
        print(json.loads(events[0].decode("utf-8")))
        

def chat_test_boto3():
    user_id = "002"
    
    payload = {'user_id': user_id, 
               'request_type': 'chatcompletion',
               'data': {'messages':
                   [{'role': 'system',
                     'content': ' 你是一名专业旅行规划师，拥有丰富的全球旅行经验和深度文化洞察力。 擅长从预算、时间、兴趣等多维度为您定制完美的个性化旅行方案。'},
                    {'role': 'user', 'content': '查询北京当前天气'}],
                   'model': 'us.amazon.nova-pro-v1:0',
                   'max_tokens': 6000, 
                   'temperature': 0.7,
                   'top_p': 0.9, 'top_k': 250, 
                   'extra_params': {'only_n_most_recent_images': 1, 
                                    'budget_tokens': 8192, 
                                    'enable_thinking': True}, 
                   'stream': True, 
                   'mcp_server_ids': ['amap-maps-sse'],
                   'tools': [], 
                   'options': {}, 
                   'keep_session': False, 
                   'mcp_server_ids': [], 
                   'use_mem': True, 
                   'use_swarm': False, 
                   'stream_id': 'stream_003_1752991306449350000'}}

    boto3_response = agentcore_client.invoke_agent_runtime(
        agentRuntimeArn=invoke_agent_arn,
        qualifier="DEFAULT",
        runtimeSessionId=generate_id_from_string(user_id),
        payload=json.dumps(payload,ensure_ascii=False)
    )
    if "text/event-stream" in boto3_response.get("contentType", ""):
        content = []
        for line in boto3_response["response"].iter_lines(chunk_size=1):
            if line:
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    line = line[6:]
                    line = json.loads(line)
                    print(line)
                #     content.append(line)
    else:
        try:
            events = []
            for event in boto3_response.get("response", []):
                events.append(event)
        except Exception as e:
            events = [f"Error reading EventStream: {e}"]
        print(json.loads(events[0].decode("utf-8")))
        

def test_http():
    
    # Get the Cognito access token
    auth_token = get_user_token(client_id="16gqg63iaqf0fhkpdc6vk0t1o9")
    print(f"Using Agent ARN: {invoke_agent_arn}")


    # Set up headers
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "X-Amzn-Trace-Id": "your-trace-id", 
        "Content-Type": "application/json",
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": "7a750a8c-11ab-447a-aec9-fe7b38402088221",
        "Accept": "text/event-stream"  # Important for SSE streaming
    }
    # Make the request with stream=True to get streaming response
    invoke_response = requests.post(
        url,
        headers=headers,
        data=json.dumps(payload, ensure_ascii=False),
        stream=True
    )

    # Print response status and headers
    print(f"Status Code: {invoke_response.status_code}")
    print(f"Response Headers: {dict(invoke_response.headers)}")

    # Process the streaming response
    if invoke_response.status_code == 200:
        print("\n--- Stream Events ---")
        
        # Simple direct parsing of the SSE stream
        for line in invoke_response.iter_lines():
            if not line:
                continue
                
            line = line.decode('utf-8')
            print(f"Raw line: {line}")
          
    else:
        print(f"Error: {invoke_response.text}")


# add_mcp_test_boto3()
chat_test_boto3()