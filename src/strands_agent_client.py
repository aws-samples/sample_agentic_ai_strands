"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
SPDX-License-Identifier: MIT-0
"""
"""
Strands Agents SDK based chat client
"""
import os
import logging
import json
import base64
from dotenv import load_dotenv
import boto3
from strands import Agent, tool
from strands.models.openai import OpenAIModel
from strands.models import BedrockModel
from chat_client import ChatClient
from mcp_client_strands import StrandsMCPClient
from strands.agent.conversation_manager import SlidingWindowConversationManager
from botocore.config import Config
from custom_tools import mem0_memory
from custom_tools.agent_core_memory import AgentCoreMemoryToolProvider
from strands_tools.code_interpreter import AgentCoreCodeInterpreter
from strands_tools.browser import AgentCoreBrowser
from custom_tools.memory_hook import AgentMemoryHooks
# from custom_tools.browser_mcp import BrowserMCPClient
from custom_tools.browser_use_tool import BrowserUseTool
from utils import generate_id_from_string
from strands.telemetry import StrandsTelemetry
from constant import *
load_dotenv()  # load environment variables from .env

import base64
import os
public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
langfuse_endpoint =  os.environ.get("LANGFUSE_HOST")
# Set up endpoint
if public_key and secret_key and langfuse_endpoint:
    otel_endpoint = langfuse_endpoint + "/api/public/otel"
    auth_token = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = otel_endpoint
    os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Basic {auth_token}"
    strands_telemetry = StrandsTelemetry()
    strands_telemetry.setup_otlp_exporter()      # Send traces to OTLP endpoint

window_size = 100
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
)
logger = logging.getLogger(__name__)
class StrandsAgentClient(ChatClient):
    """Strands Agents SDK based chat wrapper"""

    def __init__(self, credential_file='',user_id='', access_key_id='', secret_access_key='', region='', 
                 model_provider='bedrock', api_key='', api_base=None):
        # Initialize the parent ChatClient
        super().__init__(credential_file, user_id,access_key_id, secret_access_key, region)
        
        # Initialize Strands Agent
        self.model_provider = model_provider
        self.api_key = api_key or os.environ.get('OPENAI_API_KEY')
        self.api_base = api_base or os.environ.get('OPENAI_BASE_URL')
        
        # Initialize agent
        self.agent = None
        self.mcp_tools = {}  # Store MCP tools for reuse
        
        self.browser = None
        self.code_interpreter = None
        
    def _get_model(self, model_id, thinking, thinking_budget, max_tokens=1024, temperature=0.7):
        """Get the appropriate model based on provider"""
        if self.model_provider == 'openai':
            return OpenAIModel(
                client_args={
                    "api_key": self.api_key,
                    "base_url": self.api_base,
                    "timeout":900,
                },
                model_id=model_id,
                params={
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                }
            )
        elif self.model_provider == 'bedrock':
            # Create a custom boto3 session
            if self.env['AWS_ACCESS_KEY_ID']:
                session = boto3.Session(
                    aws_access_key_id=self.env['AWS_ACCESS_KEY_ID'],
                    aws_secret_access_key=self.env['AWS_SECRET_ACCESS_KEY'],
                    region_name=self.env['AWS_REGION']
                )
            else:
                session = boto3.Session(
                    region_name=self.env['AWS_REGION']
                )
            
            additional_request_fields = {
                    "thinking": {
                        "type":"enabled" if thinking else 'disabled',
                        "budget_tokens": thinking_budget,
                    }
                } if thinking else {}
            
            if model_id in [CLAUDE_4_SONNET_MODEL_ID,CLAUDE_4_OPUS_MODEL_ID]:
                additional_request_fields['anthropic_beta'] = ["interleaved-thinking-2025-05-14"]
            
            if model_id in [CLAUDE_4_SONNET_MODEL_ID,CLAUDE_4_OPUS_MODEL_ID,CLAUDE_37_SONNET_MODEL_ID,CLAUDE_35_SONNET_MODEL_ID]:
                cache_tools = "default"
            else:
                cache_tools = None
                
            if model_id in [CLAUDE_4_SONNET_MODEL_ID,CLAUDE_4_OPUS_MODEL_ID,CLAUDE_37_SONNET_MODEL_ID] and thinking:
                temperature = 1.0

            return BedrockModel(
                model_id=model_id,
                boto_session=session,
                cache_tools=cache_tools,
                cache_prompt="default",
                max_tokens=max_tokens,
                temperature=temperature,
                boto_client_config=Config(
                            read_timeout=900,
                            connect_timeout=30,
                            retries=dict(max_attempts=3, mode="adaptive"),
                            ),
                additional_request_fields=additional_request_fields,
            )
        else:
            # Default to Bedrock
            session = boto3.Session(
                aws_access_key_id=self.env['AWS_ACCESS_KEY_ID'],
                aws_secret_access_key=self.env['AWS_SECRET_ACCESS_KEY'],
                region_name=self.env['AWS_REGION']
            )
            
            return BedrockModel(
                model_id=model_id,
                boto_session=session,
                max_tokens=max_tokens,
                temperature=temperature,
                boto_client_config=Config(
                read_timeout=900,
                connect_timeout=900,
                retries=dict(max_attempts=3, mode="adaptive"),
                ),
            )
        
    def _convert_messages_to_strands_format(self, messages, system=None):
        """Convert Bedrock message format to Strands format"""
        strands_messages = []
        
        # Process messages
        for message in messages:
            role = message.get("role", "user")
            content_parts = []
            
            if isinstance(message.get("content"), list):
                for item in message["content"]:
                    if isinstance(item, dict):
                        # Handle text content
                        if "text" in item:
                            content_parts.append(item["text"])
                        
                        # Handle image content
                        elif "image" in item and "source" in item["image"]:
                            img_source = item["image"]["source"]
                            if "bytes" in img_source:
                                img_base64 = base64.b64encode(img_source["bytes"]).decode('utf-8')
                                img_format = item["image"].get("format", "png")
                                # For now, describe the image since Strands may not support images directly
                                content_parts.append(f"[Image: {img_format} format, base64 encoded]")
                        
                        # Handle tool results - convert to text
                        elif "toolResult" in item:
                            tool_result = item["toolResult"]
                            tool_content = []
                            
                            for content_item in tool_result.get("content", []):
                                if "text" in content_item:
                                    tool_content.append(content_item["text"])
                            
                            if tool_content:
                                content_parts.append(f"Tool result: {' '.join(tool_content)}")
                        
                        # Handle toolUse from assistant - convert to text
                        elif "toolUse" in item and role == "assistant":
                            tool_use = item["toolUse"]
                            tool_name = tool_use.get("name", "")
                            tool_input = tool_use.get("input", {})
                            
                            content_parts.append(f"Used tool: {tool_name} with input: {json.dumps(tool_input)}")
            elif isinstance(message.get("content"), str):
                content_parts.append(message["content"])
            
            # Join all content parts
            content = " ".join(content_parts) if content_parts else ""
            
            if content:  # Only add non-empty messages
                strands_messages.append({"role": role, "content": content})
        
        return strands_messages
    
    async def _create_mcp_tools(self, mcp_clients, mcp_server_ids):
        """Create Strands tools from MCP clients using Strands MCP client"""
        tools = []
        
        if not mcp_clients or not mcp_server_ids:
            return tools
            
        for server_id in mcp_server_ids:
            if server_id not in mcp_clients:
                continue
                
            mcp_client = mcp_clients[server_id]
            
            try:
                # Use Strands MCP client to get tools directly
                if isinstance(mcp_client, StrandsMCPClient):
                    # Get tools from Strands MCP client
                    strands_tools = mcp_client.get_tools(server_id)
                    tools.extend(strands_tools)
                    logger.info(f"Added {len(strands_tools)} Strands tools from server: {server_id}")
                else:
                    # Fallback to original method for compatibility
                    logger.warning(f"Using fallback method for non-Strands MCP client: {server_id}")
                    # This would be the original implementation if needed
                    
            except Exception as e:
                logger.error(f"Error creating tools for MCP server {server_id}: {e}")
                continue
        
        return tools
    
    def clean_builtin_tools(self):
        """clean resources of  agentcore code interpreter and browsers
        """
        logger.info("clean_builtin_tools")
        if self.code_interpreter:
            logger.info("closing code_interpreter")
            self.code_interpreter.cleanup_platform()
            elf.code_interpreter = None
        if self.browser:
            logger.info("closing browser")
            self.browser.close_platform()
            self.browser = None
            
    async def _create_agent_with_tools(self, 
                                       model_id, 
                                       messages,
                                       user_id=None,
                                       mcp_clients=None,
                                       mcp_server_ids=None, 
                                       system_prompt=None,
                                       thinking=True, 
                                       thinking_budget=4096,
                                       max_tokens=1024,
                                       temperature=0.7,
                                       use_mem=False,
                                       use_swarm=False,
                                       use_browser=False,
                                       use_code_interpreter=False):
        """Create a Strands agent with MCP tools"""
        
        # Create MCP tools
        tools = await self._create_mcp_tools(mcp_clients, mcp_server_ids)

        # Get the model
        model = self._get_model(model_id,thinking=thinking, thinking_budget=thinking_budget,max_tokens=max_tokens, temperature=temperature)
        
        agent_hooks = []

        # 如果配置了PG Database,添加memory tool
        if use_mem:
            if os.environ.get("POSTGRESQL_HOST"): 
                tools += [mem0_memory]
            elif memory_id:=os.environ.get("MEMORY_ID"): # 使用agentcore memory
                # 使用 memory hooks 
                # 单用户单session
                SESSION_ID = f"{user_id}"
                mem_hooks = AgentMemoryHooks(
                    memory_id=memory_id,
                    actor_id=user_id,
                    session_id=SESSION_ID
                )
                # add to hooks
                agent_hooks.append(mem_hooks)
                if self.memory_provider:
                    # add tools for memory
                    tools += self.memory_provider.tools
                
            else:
                logger.warning("no POSTGRESQL_HOST or AgentCore MEMORY_ID provided, memory is disabled")
        if use_code_interpreter:
            self.code_interpreter = AgentCoreCodeInterpreter(
                region=os.environ.get("AGENTCORE_REGION","us-west-2")) 
            tools += [self.code_interpreter.code_interpreter]
        
        if use_browser:
            # self.browser = BrowserMCPClient(region=os.environ.get("AGENTCORE_REGION","us-west-2"))
            # self.browser.start()
            self.browser = BrowserUseTool(region=os.environ.get("AGENTCORE_REGION","us-west-2"),model_id=model_id,use_vision=True)
            tools += self.browser.tools        
        logger.info(f"load tools:{[tool.tool_name for tool in tools]}")
        # Create agent
        agent = Agent(
            model=model,
            hooks=agent_hooks,
            # messages=messages, use agentcore mem hook
            # conversation_manager = SlidingWindowConversationManager(
            #     window_size=window_size,  # Maximum number of message pairs to keep
            # ),
            callback_handler=None,
            system_prompt=system_prompt or "You are a helpful assistant.",
            tools=tools,
            load_tools_from_directory=False
        )
        
        return agent