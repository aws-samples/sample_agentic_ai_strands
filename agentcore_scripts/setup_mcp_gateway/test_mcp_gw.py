import boto3, os
from dotenv import load_dotenv
import sys
from boto3.session import Session
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from gw_utils import get_token
cognito_client = boto3.client('cognito-idp')

assert load_dotenv(dotenv_path="../.env_cognito")
client_id = os.getenv("app_client_id")

# Authenticate User and get Access Token
auth_response = cognito_client.initiate_auth(
    ClientId=client_id,
    AuthFlow='USER_PASSWORD_AUTH',
    AuthParameters={
        'USERNAME': 'testuser',
        'PASSWORD': 'MyPassword123!'
    }
)
bearer_token = auth_response['AuthenticationResult']['AccessToken']
print(f"===========bearer_token:=========\n{bearer_token}")


async def test_mcp():
    boto_session = Session()
    region = boto_session.region_name
    
    print(f"Using AWS region: {region}")

    load_dotenv(dotenv_path=".env_mcp")
    agent_arn = os.getenv("AgentARN")
    if not agent_arn or not bearer_token:
        print("Error: AGENT_ARN or BEARER_TOKEN not retrieved properly")
        sys.exit(1)
    
    encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')
    mcp_url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
    headers = {
        "authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json"
    }
    
    print(f"\nConnecting to: {mcp_url}")
    print("Headers configured ✓")

    try:
        async with streamablehttp_client(mcp_url, headers, timeout=120, terminate_on_close=False) as (
            read_stream,
            write_stream,
            _,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                print("\n🔄 Initializing MCP session...")
                await session.initialize()
                print("✓ MCP session initialized")
                
                print("\n🔄 Listing available tools...")
                tool_result = await session.list_tools()
                
                print("\n📋 Available MCP Tools:")
                print("=" * 50)
                for tool in tool_result.tools:
                    print(f"🔧 {tool.name}")
                    print(f"   Description: {tool.description}")
                    if hasattr(tool, 'inputSchema') and tool.inputSchema:
                        properties = tool.inputSchema.get('properties', {})
                        if properties:
                            print(f"   Parameters: {list(properties.keys())}")
                    print()
                
                print(f"✅ Successfully connected to MCP server!")
                print(f"Found {len(tool_result.tools)} tools available.")
                
    except Exception as e:
        print(f"❌ Error connecting to MCP server: {e}")


async def test_gw():
    load_dotenv(dotenv_path=".env_gateway")

    user_pool_id = os.getenv("pool_id")
    m2m_client_id = os.getenv("m2m_client_id")
    m2m_client_secret = os.getenv("m2m_client_secret")
    scope_string = os.getenv("scope_string")
    gatewayURL = os.getenv("gateway_url")
    boto_session = Session()
    REGION = boto_session.region_name


    print(f"============gatewayURL:=============\n{gatewayURL}")
    token_response = get_token(user_pool_id, m2m_client_id, m2m_client_secret, scope_string, REGION)
    token = token_response["access_token"]
    print(f"===========Gateway Token:===========\n{token}")

    from strands.models import BedrockModel
    from mcp.client.streamable_http import streamablehttp_client 
    from strands.tools.mcp.mcp_client import MCPClient
    from strands import Agent

    def create_streamable_http_transport():
        return streamablehttp_client(gatewayURL, headers={"Authorization": f"Bearer {token}"})

    client = MCPClient(create_streamable_http_transport)


    with client:
        # Call the listTools 
        tools = client.list_tools_sync()
        tools_names = [tool.tool_name for tool in tools]
        print(f"Tools list from gateway are {tools_names}")

    
if __name__ == "__main__":
    try:
        asyncio.run(test_mcp())
    except Exception as e:
        print("❌ test mcp failed")
        print(str(e))
    try:
        asyncio.run(test_gw())
    except Exception as e:
        print("❌ test gateway failed")
        print(str(e))
