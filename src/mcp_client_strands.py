"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
SPDX-License-Identifier: MIT-0
"""
"""
MCP Client for Strands Agents SDK
This module provides MCP server management specifically for Strands agents.
"""
import os
import json
import logging
import asyncio
from typing import Dict, List, Optional, Any
from mcp import StdioServerParameters, stdio_client
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp import MCPClient
from strands.types.tools import AgentTool
from dotenv import load_dotenv

load_dotenv()  # load environment variables from .env

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
)
logger = logging.getLogger(__name__)

class StrandsMCPClient:
    """
    MCP Client manager for Strands Agents SDK
    
    This class handles:
    - Connecting to MCP servers using Strands MCP client
    - Managing server connections and lifecycle
    - Retrieving tools from MCP servers
    - Converting tools to Strands format
    """
    
    def __init__(self, name: str = "strands_mcp_client"):
        """Initialize the Strands MCP client manager"""
        self.name = name
        self.servers: Dict[str, Dict[str, Any]] = {}
        self.active_clients: Dict[str, MCPClient] = {}
        
    async def connect_to_server(self, server_id: str, command: str = "", server_script_path: str = "", 
                               server_script_args: List[str] = [], server_script_envs: Dict = {}, 
                               server_url: str = "", http_type: str = 'stdio', token: str = ""):
        """
        Connect to an MCP server using Strands MCP client
        
        Args:
            server_id: Unique identifier for the server
            command: Command to run the server (for stdio)
            server_script_path: Path to server script
            server_script_args: Arguments for the server script
            server_script_envs: Environment variables for the server
            server_url: URL for HTTP-based servers
            http_type: Type of HTTP transport ('sse' or 'streamable_http')
            token: Authentication token for HTTP servers
        """
        logger.info(f"connect_to_server:{server_id}:{token}")
        if server_id in self.active_clients:
            logger.warning(f"Server {server_id} is already connected")
            return
            
        try:
            # Determine transport type and create appropriate client
            if server_url:
                # HTTP-based server
                if http_type == 'sse':
                    headers = {"Authorization": f"Bearer {token}"} if token else None
                    mcp_client = MCPClient(lambda: sse_client(server_url, headers=headers))
                elif http_type == 'streamable_http':
                    headers = {"Authorization": f"Bearer {token}"} if token else None
                    mcp_client = MCPClient(lambda: streamablehttp_client(server_url, headers=headers))
                else:
                    raise ValueError(f"Unsupported HTTP transport type: {http_type}")
            else:
                # Stdio-based server
                if server_script_path:
                    # Determine command based on script type
                    is_python = server_script_path.endswith('.py')
                    is_js = server_script_path.endswith('.js')
                    is_uvx = server_script_path.startswith('uvx:')
                    is_npx = server_script_path.startswith('npx:')
                    is_docker = server_script_path.startswith('docker:')
                    is_uv = server_script_path.startswith('uv:')
                    
                    if is_uvx:
                        command = "uvx"
                        server_script_args = [server_script_path[4:]] + server_script_args
                    elif is_npx:
                        command = "npx"
                        server_script_args = ["-y", server_script_path[4:]] + server_script_args
                    elif is_uv:
                        command = "uv"
                        server_script_args = [server_script_path[3:]] + server_script_args
                    elif is_python:
                        command = command or "python"
                        server_script_args = [server_script_path] + server_script_args
                    elif is_js:
                        command = command or "node"
                        server_script_args = [server_script_path] + server_script_args
                    elif is_docker:
                        command = "docker"
                        server_script_args = [server_script_path[7:]] + server_script_args
                    else:
                        if not command:
                            raise ValueError("Command must be specified for non-standard script types")
                        server_script_args = [server_script_path] + server_script_args
                
                # Create stdio parameters
                params = StdioServerParameters(
                    command=command,
                    args=server_script_args,
                    env=server_script_envs
                )
                
                # Create MCP client with stdio transport
                mcp_client = MCPClient(lambda: stdio_client(params))
            
            # Store server configuration
            self.servers[server_id] = {
                'command': command,
                'args': server_script_args,
                'env': server_script_envs,
                'url': server_url,
                'http_type': http_type,
                'token': token,
                'client': mcp_client
            }
            
            # Store active client
            self.active_clients[server_id] = mcp_client
            
            # start server
            mcp_client.start()
            
            logger.info(f"Connected to MCP server: {server_id}")
            
        except Exception as e:
            logger.error(f"Failed to connect to MCP server {server_id}: {e}")
            raise
    
    async def disconnect_from_server(self, server_id: str):
        """
        Disconnect from an MCP server
        
        Args:
            server_id: Identifier of the server to disconnect from
        """
        if server_id not in self.active_clients:
            logger.warning(f"Server {server_id} not found or already disconnected")
            return
            
        try:
            # The MCPClient context manager handles cleanup automatically
            # We just need to remove it from our tracking
            self.active_clients[server_id].stop(None,None,None)
            del self.active_clients[server_id]
            if server_id in self.servers:
                del self.servers[server_id]
                
            logger.info(f"Disconnected from MCP server: {server_id}")
            
        except Exception as e:
            logger.error(f"Failed to disconnect from server {server_id}: {e}")
    
    def get_tools(self, server_id: str) -> List[AgentTool]:
        """
        Get tools from a specific MCP server
        
        Args:
            server_id: Identifier of the server to get tools from
            
        Returns:
            List of AgentTool objects from the server
        """
        if server_id not in self.active_clients:
            logger.error(f"Server {server_id} not active")
            return []
            
        try:
            mcp_client = self.active_clients[server_id]
            
            tools = mcp_client.list_tools_sync()
            logger.info(f"Retrieved {len(tools)} tools from server: {server_id}")
            return tools
                
        except Exception as e:
            logger.error(f"Failed to get tools from server {server_id}: {e}")
            return []
    
    def get_all_tools(self) -> List[AgentTool]:
        """
        Get tools from all active MCP servers
        
        Returns:
            Combined list of tools from all active servers
        """
        all_tools = []
        
        for server_id in self.active_clients:
            tools = self.get_tools(server_id)
            all_tools.extend(tools)
            
        logger.info(f"Retrieved {len(all_tools)} tools from all active servers")
        return all_tools
    
    async def get_tool_config(self,server_id):
        tools = self.get_tools(server_id)
        return {"tools":tools}
        
    def get_tools_for_agent(self, server_ids: List[str] = None) -> List[AgentTool]:
        """
        Get tools for use with a Strands agent
        
        Args:
            server_ids: List of server IDs to get tools from. If None, gets from all servers.
            
        Returns:
            List of AgentTool objects ready for use with Strands agents
        """
        if server_ids is None:
            return self.get_all_tools()
        
        all_tools = []
        for server_id in server_ids:
            if server_id in self.active_clients:
                tools = self.get_tools(server_id)
                all_tools.extend(tools)
            else:
                logger.warning(f"Server {server_id} not active, skipping")
        
        return all_tools
    
    async def cleanup(self):
        """Clean up all server connections"""
        server_ids = list(self.active_clients.keys())
        for server_id in server_ids:
            await self.disconnect_from_server(server_id)
        
        logger.info(f"Cleaned up all MCP server connections for {self.name}")
    
    def get_server_status(self, server_id: str) -> Dict[str, Any]:
        """
        Get status information for a server
        
        Args:
            server_id: Identifier of the server
            
        Returns:
            Dictionary containing server status information
        """
        if server_id not in self.servers:
            return {'exists': False, 'connected': False}
        
        server_config = self.servers[server_id]
        is_connected = server_id in self.active_clients
        
        return {
            'exists': True,
            'connected': is_connected,
            'command': server_config.get('command', ''),
            'args': server_config.get('args', []),
            'url': server_config.get('url', ''),
            'http_type': server_config.get('http_type', 'stdio')
        }
    
    def list_servers(self) -> List[str]:
        """
        Get list of all configured server IDs
        
        Returns:
            List of server identifiers
        """
        return list(self.servers.keys())
    
    def list_active_servers(self) -> List[str]:
        """
        Get list of all active server IDs
        
        Returns:
            List of active server identifiers
        """
        return list(self.active_clients.keys())

# Utility functions for compatibility with existing code
async def create_strands_mcp_client(name: str = "strands_mcp") -> StrandsMCPClient:
    """
    Create a new Strands MCP client instance
    
    Args:
        name: Name for the client instance
        
    Returns:
        StrandsMCPClient instance
    """
    return StrandsMCPClient(name=name)

def get_tool_name4llm(server_id: str, tool_name: str, norm: bool = True, ns_delimiter: str = "___") -> str:
    """
    Convert MCP server tool name to LLM tool call name
    
    Args:
        server_id: MCP server identifier
        tool_name: Original tool name
        norm: Whether to normalize the name
        ns_delimiter: Namespace delimiter
        
    Returns:
        Formatted tool name for LLM use
    """
    tool_key = server_id + ns_delimiter + tool_name
    if norm:
        tool_key = tool_key.replace('-', '_').replace('/', '_').replace(':', '_')
    return tool_key

def get_tool_name4mcp(tool_name4llm: str, ns_delimiter: str = "___") -> tuple:
    """
    Convert LLM tool call name back to MCP server original name
    
    Args:
        tool_name4llm: LLM tool name
        ns_delimiter: Namespace delimiter
        
    Returns:
        Tuple of (server_id, original_tool_name)
    """
    if ns_delimiter in tool_name4llm:
        parts = tool_name4llm.split(ns_delimiter, 1)
        return parts[0], parts[1]
    return "", tool_name4llm