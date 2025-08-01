"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
SPDX-License-Identifier: MIT-0
"""
"""
FastAPI server for Bedrock Chat with MCP support
"""
import os
import json
import time
import argparse
import logging
import asyncio
import base64
from fastapi import FastAPI
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Literal, AsyncGenerator, Union
import uuid
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from utils import  (get_global_server_configs,
                    get_user_server_configs,
                    session_lock,
                    save_user_server_config)
from mcp_client_strands import StrandsMCPClient
from contextlib import asynccontextmanager
from opentelemetry import baggage, context
from strands_agent_client_stream import StrandsAgentClientStream
from utils import is_endpoint_sse,save_stream_id,get_stream_id,active_streams,delete_stream_id,get_cognito_token
from data_types import *
from bedrock_agentcore.runtime import BedrockAgentCoreApp


app = BedrockAgentCoreApp()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
)
# Initialize logger
logger = logging.getLogger(__name__)


# 全局模型和服务器配置
load_dotenv()  # load env vars from .env

logger.info(f"{os.environ}")
llm_model_list = {}
shared_mcp_server_list = {}  # 共享的MCP服务器描述信息
# 用户会话存储
user_sessions = {}


MAX_TURNS = int(os.environ.get("MAX_TURNS",200))
INACTIVE_TIME = int(os.environ.get("INACTIVE_TIME",5))  #mins

COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID","")
COGNITO_CLIENT_ID=os.environ.get("COGNITO_CLIENT_ID","")
COGNITO_M2M_CLIENT_ID=os.environ.get("COGNITO_M2M_CLIENT_ID","")
COGNITO_M2M_CLIENT_SECRET=os.environ.get("COGNITO_M2M_CLIENT_SECRET","")
COGNITO_M2M_CLIENT_SCOPE=os.environ.get("COGNITO_M2M_CLIENT_SCOPE","")

def set_session_context(session_id):
    """Set the session ID in OpenTelemetry baggage for trace correlation"""
    ctx = baggage.set_baggage("session.id", session_id)
    token = context.attach(ctx)
    logging.info(f"Session ID '{session_id}' attached to telemetry context")
    return token


# 用户会话管理
class UserSession:
    def __init__(self, user_id):
        self.user_id = user_id
        self.client_type = "strands" 
        self.chat_client = StrandsAgentClientStream(
            user_id=user_id,
            model_provider=os.environ.get('STRANDS_MODEL_PROVIDER', 'bedrock'),
            api_key=os.environ.get('OPENAI_API_KEY',''),
            api_base=os.environ.get('OPENAI_BASE_URL','')
        )
        self.mcp_clients = {}  # 用户特定的MCP客户端
        self.last_active = datetime.now()
        self.session_id = str(uuid.uuid4())

    async def cleanup(self):
        """清理用户会话资源"""
        cleanup_tasks = []
        client_ids = list(self.mcp_clients.keys())
        for client_id in client_ids:
            client = self.mcp_clients[client_id]
            cleanup_tasks.append(client.cleanup())
            self.mcp_clients.pop(client_id)

        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks)
            logger.info(f"用户 {self.user_id} 的 {len(cleanup_tasks)} 个MCP客户端已清理")
    

            
async def initialize_user_servers(session: UserSession,mcp_server_ids = [],user_token=""):
    """初始化用户特有的MCP服务器"""
    user_id = session.user_id
    
    # 获取用户服务器配置（现在是异步方法）
    server_configs = await get_user_server_configs(user_id)
    
    global_server_configs = get_global_server_configs()
    # 合并全局和用户的servers
    server_configs = {**server_configs, **global_server_configs}
    
    # logger.info(f"server_configs:{server_configs}")
    
    # 初始化agentcore gateway m2m token
    m2m_token = ""
    # 初始化服务器连接
    for server_id, config in server_configs.items():
        # 如果不在用户的请求request中，则跳过
        if server_id not in mcp_server_ids:
            continue
        if server_id in session.mcp_clients:  # 跳过已存在的服务器
            logger.info(f"skip {server_id} initialization ")
            continue
            
        try:
            # 创建并连接MCP服务器
            if session.client_type == 'strands':
                mcp_client = StrandsMCPClient(name=f"{session.user_id}_{server_id}")
            else:
                raise ValueError("only support client_type strands")
            server_url = config.get('url',"")
            # token = user_token if config.get('token') == "" else config.get('token')
            token = config.get('token','') 

            # it is from agentcore
            if 'bedrock-agentcore' in server_url :
                # if it is agentcore mcp runtime use user_token pass in from client
                if "/invocations?qualifier" in server_url and not token:
                    token = user_token
                    logger.info(f"Get mcp token:{token}")
                # if it is gateway 
                elif 'gateway.bedrock-agentcore' in server_url and not token and not m2m_token:
                    m2m_token = get_cognito_token(user_pool_id=COGNITO_USER_POOL_ID,
                                  client_id=COGNITO_M2M_CLIENT_ID,
                                  client_secret=COGNITO_M2M_CLIENT_SECRET,
                                  scope_string=COGNITO_M2M_CLIENT_SCOPE)
                    token = m2m_token["access_token"]
                    # logger.info("Get agentcore gateway token:{token}")

                else:
                    raise ValueError('Cannot recognize the url type in bedrock agentcore')                
                
            await mcp_client.connect_to_server(
                server_id=server_id,
                command=config.get('command'),
                server_url=server_url,
                http_type= "sse" if is_endpoint_sse(server_url) else "streamable_http" ,
                token=token,
                server_script_args=config.get("args", []),
                server_script_envs=config.get("env", {})
            )
            
            # 添加到用户的客户端列表
            session.mcp_clients[server_id] = mcp_client
            await save_user_server_config(user_id, server_id, config)
            logger.info(f"User Id {session.user_id} initialize server {server_id}")
            
        except Exception as e:
            logger.error(f"User Id  {session.user_id} initialize server {server_id} failed: {e}")


async def get_or_create_user_session(
    user_id: str,
    init_mcp = True,
    mcp_server_ids = [],
    user_token :str = "",
):
    """获取或创建用户会话，并自动初始化用户服务器"""
    global user_sessions
    
    if user_id not in user_sessions: 
        session =  UserSession(user_id)           
        # 更新最后活跃时间
        session.last_active = datetime.now()
        user_sessions[user_id] = session
        logger.info(f"为用户 {user_id} 创建新会话: {user_sessions[user_id].session_id}")
    else:
        session =  user_sessions[user_id]
    # 从ddb中取出配置，重新初始化，如果已经存在则跳过。
    if init_mcp:
        await initialize_user_servers(session,mcp_server_ids,user_token)
    return session


async def cleanup_inactive_sessions():
    """定期清理不活跃的用户会话"""
    while True:
        await asyncio.sleep(10)  # 每10s检查一次
        current_time = datetime.now()
        inactive_users = []
        
        # 找出不活跃的用户
        with session_lock:
            for user_id, session in user_sessions.items():
                if (current_time - session.last_active) > timedelta(minutes=INACTIVE_TIME):
                    inactive_users.append(user_id)
        
        for user_id in inactive_users:
            with session_lock:
                if user_id in user_sessions:
                    session = user_sessions.pop(user_id)
                    try:
                        await session.cleanup()
                    except Exception as e:
                        logger.error(f"清理用户 {user_id} 会话失败: {e}")
        
        if inactive_users:
            logger.info(f"已清理 {len(inactive_users)} 个不活跃用户会话")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """服务器启动时执行的任务"""
    # 启动其他初始化任务
    await startup_event()
    yield
     # 清理和保存状态
    await shutdown_event()
    
async def startup_event():
    """服务器启动时执行的任务"""
    # 启动会话清理任务
    asyncio.create_task(cleanup_inactive_sessions())

async def shutdown_event():
    """服务器关闭时执行的任务"""
    # 清理所有会话
    cleanup_tasks = []
    with session_lock:
        for user_id, session in user_sessions.items():
            cleanup_tasks.append(session.cleanup())
    
    if cleanup_tasks:
        await asyncio.gather(*cleanup_tasks)
        logger.info(f"已清理所有 {len(cleanup_tasks)} 个用户会话")
        
        
async def stream_chat_response(data: ChatCompletionRequest, session: UserSession, stream_id: str = None) -> AsyncGenerator[str, None]:
    """为特定用户生成流式聊天响应"""
    
    # 注册流
    if stream_id:
        try:
            # 先在ChatClientStream中注册流，然后再添加到active_streams
            await save_stream_id(stream_id=stream_id,user_id=session.user_id)
            logger.info(f"Stream {stream_id} registered for user {session.user_id}")
            logger.info(f"active_streams:{active_streams}")
        except Exception as e:
            logger.error(f"Error registering stream {stream_id}: {e}")

    # Process messages with possible structured content
    messages = []
    for file_idx, msg in enumerate(data.messages):
        message_content = []
        
        # Handle string content (backward compatibility)
        if isinstance(msg.content, str):
            message_content = [{"text": msg.content}]
        # Handle structured content (OpenAI format)
        else:
            for content_item in msg.content:
                # Text content
                if content_item.type == "text":
                    message_content.append({"text": content_item.text})
                
                # Image content
                elif content_item.type == "image_url":
                    image_url = content_item.image_url.url
                    
                    # Handle base64 encoded images
                    if image_url.startswith("data:image/"):
                        try:
                            # Parse data URI format: data:image/png;base64,ABC123...
                            parts = image_url.split(";base64,")
                            if len(parts) == 2:
                                img_format = parts[0].split("/")[1]
                                base64_data = parts[1]
                                img_bytes = base64.b64decode(base64_data)
                                
                                message_content.append({
                                    "image": {
                                        "format": img_format,
                                        "source": {
                                            "bytes": img_bytes
                                        }
                                    }
                                })
                        except Exception as e:
                            logger.error(f"Error processing base64 image: {e}")
                    else:
                        logger.warning(f"External image URLs not supported yet: {image_url}")
                
                # File content
                elif content_item.type == "file":
                    file_obj = content_item.file
                    
                    # Handle base64 encoded file data
                    if file_obj.file_data:
                        try:
                            file_data = base64.b64decode(file_obj.file_data)
                            filename = file_obj.filename or "unnamed_file"
                            # Determine file format from filename or mime type
                            file_ext = os.path.splitext(filename)[1].lower().replace(".", "")
                            if not file_ext:
                                file_ext = "txt"  # Default to txt if no extension
                                
                            # Map to Bedrock document format
                            doc_format_map = {
                                "pdf": "pdf",
                                "csv": "csv", 
                                "doc": "doc",
                                "docx": "docx",
                                "xls": "xls", 
                                "xlsx": "xlsx",
                                "html": "html",
                                "txt": "txt",
                                "md": "md",
                                "json": "txt",  # JSON treated as text
                                "xml": "txt",   # XML treated as text
                                "py": "txt",    # Python file treated as text
                                "js": "txt",    # JS file treated as text
                                "ts": "txt",    # TS file treated as text
                            }
                            
                            doc_format = doc_format_map.get(file_ext, "txt")
                            
                            message_content.append({
                                "document": {
                                    "format": doc_format,
                                    "name": f"files_{file_idx}",
                                    "source": {
                                        "bytes": file_data
                                    }
                                }
                            })
                        except Exception as e:
                            logger.error(f"Error processing file data: {e}")
                    
                    # Handle file_id (not implemented in this version)
                    elif file_obj.file_id:
                        logger.warning(f"File ID references not implemented yet: {file_obj.file_id}")
        
        messages.append({
            "role": msg.role,
            "content": message_content
        })
    
    system = []
    if messages and messages[0]['role'] == 'system':
        system = messages[0]['content'] if messages[0]['content'] else []
        messages = messages[1:]

    # bedrock's first turn cannot be assistant
    if messages and messages[0]['role'] == 'assistant':
        messages = messages[1:]
    
    try:
        current_content = ""
        thinking_start = False
        thinking_text_index = 0
        tooluse_start = False
    
        
        response_stream = session.chat_client.process_query_stream(
            model_id=data.model,
            user_id=session.user_id,
            max_tokens=data.max_tokens,
            temperature=data.temperature,
            messages=messages,
            system=system,
            max_turns=MAX_TURNS,
            mcp_clients=session.mcp_clients,
            mcp_server_ids=data.mcp_server_ids,
            extra_params=data.extra_params,
            keep_session=data.keep_session,
            stream_id=stream_id
        )
        
        async for item in response_stream:
            if isinstance(item, dict):  # 来自 process_query_stream 的响应
                response = item
                # logger.info(f"{response}")
                event_data = {
                    "id": f"chat{time.time_ns()}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": data.model,
                    "choices": [{
                        "index": 0,
                        "delta": {},
                        "finish_reason": None
                    }]
                }
                
                # 处理不同的事件类型
                if response["type"] == "message_start":
                    event_data["choices"][0]["delta"] = {"role": "assistant"}
                    
                elif response["type"] == "block_start":
                    block_start = response["data"]
                    if "toolUse" in block_start.get("start", {}):
                        event_data["choices"][0]["message_extras"] = {
                            "tool_name": block_start["start"]["toolUse"]["name"]
                        }
                    
                elif response["type"] == "block_delta":
                    if "text" in response["data"]["delta"]:
                        text = ""
                        text += str(response["data"]["delta"]["text"])
                        current_content += text
                        event_data["choices"][0]["delta"] = {"content": text}
                        thinking_text_index = 0
                        
                    if "toolUse" in response["data"]["delta"]:
                        # text = ""
                        if not tooluse_start:    
                            tooluse_start = True
                        event_data["choices"][0]["delta"] = {"toolinput_content": response["data"]["delta"]["toolUse"]['input']}
                        
                    if "reasoningContent" in response["data"]["delta"]:
                        if 'text' in response["data"]["delta"]["reasoningContent"]:
                            event_data["choices"][0]["delta"] = {"reasoning_content": response["data"]["delta"]["reasoningContent"]["text"]}
                            

                elif response["type"] == "block_stop":
                    if tooluse_start:
                        tooluse_start = False
                        event_data["choices"][0]["delta"] = {"toolinput_content": "<END>"}
                        
                elif response["type"] in [ "message_stop" ,"result_pairs"]:
                    event_data["choices"][0]["finish_reason"] = response["data"]["stopReason"]
                    if response["data"].get("tool_results"):
                        event_data["choices"][0]["message_extras"] = {
                            "tool_use": json.dumps(response["data"]["tool_results"],ensure_ascii=False)
                        }

                elif response["type"] == "error":
                    event_data["choices"][0]["finish_reason"] = "error"
                    event_data["choices"][0]["delta"] = {
                        "content": f"Error: {response['data']}"
                    }
                     # 抛出异常
                    raise Exception(response['data'])
                elif response["type"] == "heatbeat":
                    yield f": heartbeat\n\n"

                # 发送事件
                yield f"data: {json.dumps(event_data)}\n\n"
                    
                # 手动停止流式响应
                if response["type"] == "stopped":
                    event_data = {
                        "id": f"stop{time.time_ns()}",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": data.model,
                        "choices": [{
                            "index": 0,
                            "delta": {},
                            "finish_reason": "stop_requested"
                        }]
                    }
                    yield f"data: {json.dumps(event_data)}\n\n"
                    yield "data: [DONE]\n\n"
                    break
                
                # 发送结束标记
                if response["type"] == "message_stop" and response["data"]["stopReason"] in ['end_turn','max_tokens']:
                    if response["data"]["stopReason"] == 'max_tokens':
                        event_data = {
                            "id": f"stop{time.time_ns()}",
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": data.model,
                            "choices": [{
                                "index": 0,
                                "delta": {"content":"<max output token reached>"},
                                "finish_reason": "max_tokens"
                            }]
                        }
                        yield f"data: {json.dumps(event_data)}\n\n"
                    elif response["data"]["stopReason"] == 'end_turn':
                        event_data = {
                            "id": f"stop{time.time_ns()}",
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": data.model,
                            "choices": [{
                                "index": 0,
                                "delta": {},
                                "finish_reason": "end_turn"
                            }]
                        }
                        yield f"data: {json.dumps(event_data)}\n\n"
                        
                    yield "data: [DONE]\n\n"
                    break
            

    except Exception as e:
        logger.error(f"Stream error for user {session.user_id}: {e}",exc_info=True)
        error_message = f"Stream processing error: {type(e).__name__} - {str(e)}"
        error_data = {
            "id": f"error{time.time_ns()}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": data.model,
            "choices": [{
                "index": 0,
                "delta": {"content": f"Error: {error_message}"},
                "finish_reason": "error"
            }]
        }
        yield f"data: {json.dumps(error_data)}\n\n"
        yield "data: [DONE]\n\n"
        
    finally:
        # 清除活跃流列表中的请求
        try:
            if stream_id:
                # 清理同步：先从ChatClientStream中删除，再从active_streams中删除
                session.chat_client.unregister_stream(stream_id)
                await delete_stream_id(stream_id)
                logger.info(f"Stream {stream_id} unregistered")
        except Exception as e:
            logger.error(f"Error cleaning up stream {stream_id}: {e}")

async def remove_history(
    user_id:str,
):
    # 获取用户会话
    session = await get_or_create_user_session(user_id,init_mcp=False)
    if session:
        logger.info("remove_history")
        await session.chat_client.clear_history()
        

async def stop_stream(
    user_id: str,
    data: StopStreamRequest
):
    """停止正在进行的模型输出流"""
    global active_streams, user_sessions
    stream_id = data.stream_id
    logger.info(f"stopping request:{stream_id} in {active_streams}")
    # 获取用户会话
    session = user_sessions.get(user_id)     
    if not stream_id in active_streams or not session:
        # 如果不在当前的实例中，则直接remove ddb中的数据
        try:
            await delete_stream_id(stream_id=stream_id)
            logger.info(f"Removed {stream_id} from remote record")
        except Exception as e:
            logger.error(f"Error removing stream from active_streams: {e}")
        return
    elif session:
        user_id = session.user_id
        # 检查流是否存在且属于当前用户
        stream_id_result = await get_stream_id(stream_id)
        if  stream_id_result != user_id:
            logger.warning(f"Stream {stream_id} not found in user_id:{user_id}, not authorized to stop this stream")
            return
        
        # 使用BackgroundTasks处理停止流的操作，确保即使客户端断开连接，流也能被正确停止
        async def stop_stream_task(stream_id, session):
            try:
                # 调用流停止功能，即使流可能已经结束
                success = session.chat_client.stop_stream(stream_id)
                if success:
                    logger.info(f"Successfully initiated stop for stream {stream_id}")
                    # 在异步任务中安全地更新共享状态
                    try:
                        await delete_stream_id(stream_id=stream_id)
                        logger.info(f"Removed {stream_id} from active_streams")
                    except Exception as e:
                        logger.error(f"Error removing stream from active_streams: {e}")
                else:
                    logger.warning(f"Failed to stop stream {stream_id}")
                    # 即使返回失败也尝试从活跃流列表中移除，防止僵尸流
                    try:
                        await delete_stream_id(stream_id=stream_id)
                        logger.info(f"Removed {stream_id} from active_streams")
                    except Exception as e:
                        logger.error(f"Error removing stream from active_streams: {e}")
                        
            except Exception as e:
                logger.error(f"Error in background task stopping stream {stream_id}: {e}")
        
        await stop_stream_task(stream_id, session)
        logger.info(f"Started stop thread for stream: {stream_id}")

async def chat_completions(
    user_id:str,
    data:ChatCompletionRequest,
    
):
    mcp_server_ids = data.mcp_server_ids
    # Set session context for telemetry
    # context_token = set_session_context(user_id)
    # user token for agentcore mcp
    user_token = data.token if data.token else ""
    # 获取用户会话
    session = await get_or_create_user_session(user_id=user_id,mcp_server_ids=mcp_server_ids,user_token=user_token)
    # logger.info(session)
    # 记录会话活动
    session.last_active = datetime.now()
    stream_id = data.stream_id
    async for event in stream_chat_response(data, session, stream_id):
        await asyncio.sleep(0.001)
        yield event
        # 更新active time
        session.last_active = datetime.now()

     # Detach context when done
    # context.detach(context_token)
        
@app.entrypoint
async def entry(payload:OperationsRequest):
    request = OperationsRequest(**payload)
    user_id = request.user_id
    data = request.data
    logger.info(f"=====request type:{request.request_type}=======\n")
    # Use model_dump_json() for Pydantic v2 or json() for Pydantic v1
    logger.info(f"=====request data=======\n{data.model_dump_json()}")
    if request.request_type == 'chatcompletion':
        async for event in chat_completions(user_id,data):
            yield event
    elif request.request_type == "stopstream":
        await stop_stream(user_id,data)
        yield "stopping\n\n"
    elif request.request_type == "removehistory":
        await remove_history(user_id)
        yield "remove history\n\n"

if __name__ == '__main__':
    app.run()

    


        
    
