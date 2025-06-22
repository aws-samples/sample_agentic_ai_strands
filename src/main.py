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
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Literal, AsyncGenerator, Union
import uuid
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Security
from utils import  (get_global_server_configs,
                    delete_user_message,
                    save_global_server_config,
                    delete_user_server_config,
                    get_user_server_configs,
                    load_user_mcp_configs,
                    session_lock,
                    DDB_TABLE,
                    save_user_server_config)
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from mcp_client_strands import StrandsMCPClient
from strands_agent_client_stream import StrandsAgentClientStream
from fastapi import APIRouter
from utils import is_endpoint_sse,save_stream_id,get_stream_id,active_streams,delete_stream_id,delete_user_session,get_user_session,save_user_session
from data_types import *
from health import router as health_router

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
)
# Initialize logger
logger = logging.getLogger(__name__)


# 全局模型和服务器配置
load_dotenv()  # load env vars from .env

llm_model_list = {}
shared_mcp_server_list = {}  # 共享的MCP服务器描述信息
# 用户会话存储
user_sessions = {}


MAX_TURNS = int(os.environ.get("MAX_TURNS",200))
INACTIVE_TIME = int(os.environ.get("INACTIVE_TIME",60*24))  #mins
API_KEY = os.environ.get("API_KEY")

security = HTTPBearer()


# 用户会话管理
class UserSession:
    def __init__(self, user_id):
        self.user_id = user_id
        self.client_type = "strands" # os.environ.get('CLIENT_TYPE', 'strands') 
        client_type = self.client_type
        
        if client_type == 'strands':
            self.chat_client = StrandsAgentClientStream(
                user_id=user_id,
                model_provider=os.environ.get('STRANDS_MODEL_PROVIDER', 'bedrock'),
                api_key=os.environ.get('OPENAI_API_KEY'),
                api_base=os.environ.get('OPENAI_BASE_URL')
            )
        else:
            raise ValueError("Please go for MCP on Bedrock Version")

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
    


async def get_api_key(auth: HTTPAuthorizationCredentials = Security(security)):
    if auth.credentials == API_KEY:
        return auth.credentials
    raise HTTPException(status_code=403, detail="Could not validate credentials")

            
async def initialize_user_servers(session: UserSession):
    """初始化用户特有的MCP服务器"""
    user_id = session.user_id
    
    # 获取用户服务器配置（现在是异步方法）
    server_configs = await get_user_server_configs(user_id)
    
    global_server_configs = get_global_server_configs()
    # 合并全局和用户的servers
    server_configs = {**server_configs, **global_server_configs}
    
    logger.info(f"server_configs:{server_configs}")
    # 初始化服务器连接
    for server_id, config in server_configs.items():
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
            
            await mcp_client.connect_to_server(
                server_id=server_id,
                command=config.get('command'),
                server_url=server_url,
                http_type= "sse" if is_endpoint_sse(server_url) else "streamable_http" ,
                token=config.get('token', None),
                server_script_args=config.get("args", []),
                server_script_envs=config.get("env", {})
            )
            
            # 添加到用户的客户端列表
            session.mcp_clients[server_id] = mcp_client
            await save_user_server_config(user_id, server_id, config)
            logger.info(f"User Id {session.user_id} initialize server {server_id}")
            
        except Exception as e:
            logger.error(f"User Id  {session.user_id} initialize server {server_id} failed: {e}")
    # 保存配置        
    # await save_user_mcp_configs()

async def get_or_create_user_session(
    request: Request,
    auth: HTTPAuthorizationCredentials = Security(security),
    create_new = True
):
    """获取或创建用户会话，优先使用X-User-ID头，并自动初始化用户服务器"""
    global user_sessions
    # 先验证API密钥
    await get_api_key(auth)
    
    # 尝试从请求头获取用户ID，如果不存在则使用API密钥作为备用ID
    user_id = request.headers.get("X-User-ID", auth.credentials)
    
    session_obj = await get_user_session(user_id)
    if not session_obj and not create_new:
        return None
    
    is_in_local = True if user_id in user_sessions else False
    
    # 如果全局都没有
    if not session_obj:
        await save_user_session(user_id,dict(user_id=user_id))
        if user_id not in user_sessions:
            user_sessions[user_id] = UserSession(user_id)
            logger.info(f"为用户 {user_id} 创建新会话: {user_sessions[user_id].session_id}")
    
    # 如果已经在全局中，但是不在本地，则在本地new session
    if not is_in_local and session_obj: 
        user_sessions[user_id] = UserSession(user_id)
        logger.info(f"为用户 {user_id} 创建新会话: {user_sessions[user_id].session_id}")
    
    # 更新最后活跃时间
    user_sessions[user_id].last_active = datetime.now()
    session = user_sessions[user_id]
    
    # 从ddb中取出配置，重新初始化，如果已经存在则跳过。
    await initialize_user_servers(session)

    # 如果是新会话，初始化用户的MCP服务器
    # if not session_obj:
    #     await initialize_user_servers(session)
    # elif not is_in_local and session_obj: # 如果已经在全局中，但是不在本地，也需要初始化
    #     await initialize_user_servers(session)
    # elif not session.mcp_clients:# 如果用户的MCP服务器已经为空，则重新初始化
    #     await initialize_user_servers(session)
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
                    await delete_user_session(user_id)
                    try:
                        await session.cleanup()
                    except Exception as e:
                        logger.error(f"清理用户 {user_id} 会话失败: {e}")
        
        if inactive_users:
            logger.info(f"已清理 {len(inactive_users)} 个不活跃用户会话")



@asynccontextmanager
async def lifespan(app: FastAPI):
    """服务器启动时执行的任务"""
    # 加载持久化的用户MCP配置
    await load_user_mcp_configs()
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
    # 保存用户MCP配置
    # await save_user_mcp_configs()
    
    # 清理所有会话
    cleanup_tasks = []
    with session_lock:
        for user_id, session in user_sessions.items():
            cleanup_tasks.append(session.cleanup())
    
    if cleanup_tasks:
        await asyncio.gather(*cleanup_tasks)
        logger.info(f"已清理所有 {len(cleanup_tasks)} 个用户会话")


app = FastAPI(lifespan=lifespan)

# 添加CORS中间件支持跨域请求和自定义头
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应限制为特定的前端域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],  # 允许所有头，包括自定义的X-User-ID
)

# 配置单独的路由组，确保停止路由不受streaming路由的并发限制影响
stop_router = APIRouter()
list_router = APIRouter()

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    logger.error(f"Validation error: {exc}")
    return JSONResponse(content=AddMCPServerResponse(
                errno=422,
                msg=str(exc.errors())
            ).model_dump())

@list_router.get("/v1/list/models")
async def list_models(
    request: Request,
    auth: HTTPAuthorizationCredentials = Security(security)
):
    # 只需验证API密钥，不需要用户会话
    await get_api_key(auth)
    return JSONResponse(content={"models": [{
        "model_id": mid, 
        "model_name": name} for mid, name in llm_model_list.items()]})

@list_router.get("/v1/list/mcp_server")
async def list_mcp_server(
    request: Request,
    auth: HTTPAuthorizationCredentials = Security(security)
):
    await get_api_key(auth)
    # 获取用户会话
    session = await get_or_create_user_session(request, auth)
    
    # 合并全局和用户特定的服务器列表
    server_list = {**shared_mcp_server_list}
    
    # 添加用户特有的服务器
    for server_id in session.mcp_clients:
        if server_id not in server_list:
            server_list[server_id] = f"User-specific server: {server_id}"
    
    return JSONResponse(content={"servers": [{
        "server_id": sid, 
        "server_name": name} for sid, name in server_list.items()]})

# 将stop_router包含在主应用中, 注意这个顺序必须在接口定义之后
app.include_router(list_router)

@stop_router.post("/v1/remove/history")
async def remove_history(
    request: Request,
    background_tasks: BackgroundTasks,
    auth: HTTPAuthorizationCredentials = Security(security)
):
    # 获取用户会话
    await get_api_key(auth)
    
    # 尝试从请求头获取用户ID，如果不存在则使用API密钥作为备用ID
    user_id = request.headers.get("X-User-ID", auth.credentials)
    
    # 直接从ddb里删除记录即可
    if DDB_TABLE:
        await delete_user_message(user_id)
        return JSONResponse(
                content={"errno": 0, "msg": "removed history"},
                # 添加特殊的响应头，使浏览器不缓存此响应
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
    else:
        session = await get_or_create_user_session(request, auth,create_new=False)
        if not session:
            # 没有找到session立即返回响应给客户端
            return JSONResponse(
                content={"errno": 0, "msg": "remove history from empty session"},
                # 添加特殊的响应头，使浏览器不缓存此响应
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
        else:
            await session.chat_client.clear_history()
            # await session.cleanup()
            return JSONResponse(
                content={"errno": 0, "msg": "removed history"},
                # 添加特殊的响应头，使浏览器不缓存此响应
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )

# 使用单独的路由器处理stop请求，以避免被streaming请求阻塞
@stop_router.post("/v1/stop/stream/{stream_id}")
async def stop_stream(
    stream_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    auth: HTTPAuthorizationCredentials = Security(security)
):
    """停止正在进行的模型输出流"""
    global active_streams
    logger.info(f"stopping request:{stream_id} in {active_streams}")
    if not stream_id in active_streams:
        # 如果不在当前的实例中，则直接remove ddb中的数据
        try:
            await delete_stream_id(stream_id=stream_id)
            logger.info(f"Removed {stream_id} from remote record")
        except Exception as e:
            logger.error(f"Error removing stream from active_streams: {e}")
        return JSONResponse(
            content={"errno": 0, "msg": "Stream stopping initiated"},
            # 添加特殊的响应头，使浏览器不缓存此响应
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    
    try:
        # 获取用户会话
        session = await get_or_create_user_session(request, auth)
        user_id = session.user_id
        
        # 检查流是否存在且属于当前用户
        authorized = True
        if await get_stream_id(stream_id) != user_id:
            authorized = False
            
        saved_user_id = await get_stream_id(stream_id)
        if saved_user_id:
            if saved_user_id != user_id:
                authorized = False
        else:
            # 流ID不在活跃列表中，但我们仍然尝试停止它
            logger.warning(f"Stream {stream_id} not found in active_streams but still trying to stop it")
        
        if not authorized:
            return JSONResponse(content={"errno": -1, "msg": "Not authorized to stop this stream"})
        
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
        
        # 添加后台任务
        background_tasks.add_task(stop_stream_task, stream_id, session)
        
        # 立即返回响应给客户端
        return JSONResponse(
            content={"errno": 0, "msg": "Stream stopping initiated"},
            # 添加特殊的响应头，使浏览器不缓存此响应
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
        
    except Exception as e:
        logger.error(f"Error stopping stream {stream_id}: {e}")
        return JSONResponse(content={"errno": -1, "msg": f"Error stopping stream: {str(e)}"})

# 将stop_router包含在主应用中, 注意这个顺序必须在接口定义之后
app.include_router(stop_router)
app.include_router(health_router)

@app.post("/v1/add/mcp_server")
async def add_mcp_server(
    request: Request,
    data: AddMCPServerRequest,
    background_tasks: BackgroundTasks,
    auth: HTTPAuthorizationCredentials = Security(security)
):
    global shared_mcp_server_list
    # 获取用户会话
    session = await get_or_create_user_session(request, auth)
    user_id = session.user_id
    
    # 使用会话锁确保操作是线程安全的
    # async with session.lock:
    if data.server_id in session.mcp_clients:
        return JSONResponse(content=AddMCPServerResponse(
            errno=-1,
            msg="MCP server id exists for this user!"
        ).model_dump())
    
    server_id = data.server_id
    server_cmd = data.command
    server_script_args = data.args
    server_script_envs = data.env
    server_desc = data.server_desc if data.server_desc else data.server_id
    
    # 处理配置JSON
    if data.config_json:
        config_json = data.config_json
        if not all([isinstance(k, str) for k in config_json.keys()]):
            return JSONResponse(content=AddMCPServerResponse(
                errno=-1,
                msg="env key must be str!"
            ).model_dump())
            
        if "mcpServers" in config_json:
            config_json = config_json["mcpServers"]
            
        server_id = list(config_json.keys())[0]
        server_cmd = config_json[server_id].get("command","")
        server_url = config_json[server_id].get("url","")
        server_script_args = config_json[server_id].get("args",[])
        server_script_envs = config_json[server_id].get('env',{})
        http_type= "sse" if is_endpoint_sse(server_url) else "streamable_http"
        token=config_json[server_id].get('token', None)
        
    # 连接MCP服务器
    tool_conf = {}
    try:
        # 创建客户端对象移到try块内
        if session.client_type == 'strands':
            mcp_client = StrandsMCPClient(name=f"{session.user_id}_{server_id}")
        else:
            raise ValueError('only support strands')
        
        # 添加超时控制
        connect_task = mcp_client.connect_to_server(
            server_id=server_id,
            command=server_cmd,
            server_url=server_url,
            http_type=http_type,
            token=token,
            server_script_args=server_script_args,
            server_script_envs=server_script_envs
        )
        
        # 设置60秒超时
        await asyncio.wait_for(connect_task, timeout=120.0)
        
        tool_conf = await mcp_client.get_tool_config(server_id=server_id)
        logger.info(f"User {session.user_id} connected to MCP server {server_id}, tools={tool_conf}")
        
        # 保存用户服务器配置以便将来恢复
        server_config = {
            "url":server_url,
            "command": server_cmd,
            "args": server_script_args,
            "env": server_script_envs,
            "description": server_desc,
            "token":token
        }
        await save_user_server_config(user_id, server_id, server_config)
        
        # 成功连接后才将客户端添加到用户会话
        session.mcp_clients[server_id] = mcp_client
        
    except asyncio.TimeoutError:
        logger.error(f"连接MCP服务器 {server_id} 超时")
        # 清理超时的连接资源
        try:
            await mcp_client.cleanup()
        except Exception as cleanup_error:
            logger.error(f"清理超时连接资源失败: {cleanup_error}")
        return JSONResponse(content=AddMCPServerResponse(
            errno=-1,
            msg="MCP server connection timeout!"
        ).model_dump())
    except Exception as e:
        logger.error(f"User {session.user_id} connect to MCP server {server_id} error: {e}")
        # 清理失败的连接资源
        try:
            await mcp_client.cleanup()
        except Exception as cleanup_error:
            logger.error(f"清理失败连接资源出错: {cleanup_error}")
        return JSONResponse(content=AddMCPServerResponse(
            errno=-1,
            msg=f"MCP server connect failed: {str(e)}"
        ).model_dump())

    # await save_user_mcp_configs()
    return JSONResponse(content=AddMCPServerResponse(
        errno=0,
        msg="The server already been added!",
        # data={"tools": tool_conf.get("tools", {}) if tool_conf else {}}
    ).model_dump())

@app.delete("/v1/remove/mcp_server/{server_id}")
async def remove_mcp_server(
    server_id: str,
    request: Request,
    auth: HTTPAuthorizationCredentials = Security(security)
):
    """删除用户的MCP服务器"""
    # 获取用户会话
    session = await get_or_create_user_session(request, auth)
    user_id = session.user_id
    
    # 使用会话锁确保操作是线程安全的
    # async with session.lock:
    if server_id not in session.mcp_clients:
        logger.warning(f"User {user_id} tried to remove non-existent server {server_id}")        
        # 从用户配置中删除
        await delete_user_server_config(user_id, server_id)
        logger.info(f"User {user_id} removed MCP server {server_id}")
        return JSONResponse(content=AddMCPServerResponse(
            errno=0,
            msg="Server removed successfully"
        ).model_dump())
        
    try:
        # async with session.lock:
        # 清理资源
        await session.mcp_clients[server_id].disconnect_from_server(server_id)
        # 移除服务器
        del session.mcp_clients[server_id]

        # 从用户配置中删除
        await delete_user_server_config(user_id, server_id)
        logger.info(f"User {user_id} removed MCP server {server_id}")
            
        
        return JSONResponse(content=AddMCPServerResponse(
            errno=0,
            msg="Server removed successfully"
        ).model_dump())
        
    except Exception as e:
        logger.error(f"User {user_id} remove MCP server {server_id} error: {e}")
        return JSONResponse(content=AddMCPServerResponse(
            errno=-1,
            msg=f"Failed to remove server: {str(e)}"
        ).model_dump())


async def stream_chat_response(data: ChatCompletionRequest, session: UserSession, stream_id: str = None) -> AsyncGenerator[str, None]:
    """为特定用户生成流式聊天响应"""
    
    # 注册流
    if stream_id:
        try:
            # 先在ChatClientStream中注册流，然后再添加到active_streams
            await save_stream_id(stream_id=stream_id,user_id=session.user_id)
            # logger.info(f"Stream {stream_id} registered for user {session.user_id}")
            logger.info(f"active_streams:{active_streams}")
        except Exception as e:
            logger.error(f"Error registering stream {stream_id}: {e}")
    
    # 心跳任务控制
    heartbeat_task = None
    heartbeat_stop_event = asyncio.Event()
    
    async def heartbeat_sender():
        """独立的心跳发送任务"""
        try:
            while not heartbeat_stop_event.is_set():
                await asyncio.sleep(30)  # 每30秒发送一次心跳，减少频率
                if not heartbeat_stop_event.is_set():
                    logger.debug("sse heartbeat")  # 改为debug级别，减少日志噪音
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
    
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
    
        
        # 创建合并的异步生成器，同时处理响应流和心跳
        response_stream = session.chat_client.process_query_stream(
            model_id=data.model,
            max_tokens=data.max_tokens,
            temperature=data.temperature,
            messages=messages,
            system=system,
            max_turns=MAX_TURNS,
            mcp_clients=session.mcp_clients,
            mcp_server_ids=data.mcp_server_ids,
            extra_params=data.extra_params,
            keep_session=data.keep_session,
            stream_id=stream_id,
        )
        
        # 创建心跳生成器
        heartbeat_gen = heartbeat_sender()
        
        # 使用合并流来处理响应和心跳
        async for item in _merge_streams(response_stream, heartbeat_gen):
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
                
                elif response["type"] == "block_delta":
                    if "text" in response["data"]["delta"]:
                        text = ""
                        if thinking_text_index >= 1 and thinking_start:    
                            thinking_start = False
                            text = "</thinking>"
                        text += response["data"]["delta"]["text"]
                        current_content += text
                        event_data["choices"][0]["delta"] = {"content": text}
                        thinking_text_index = 0
                        
                    if "toolUse" in response["data"]["delta"]:
                        text = ""
                        if not tooluse_start:    
                            tooluse_start = True
                            text = "<tool_input>"
                        text += response["data"]["delta"]["toolUse"]['input']
                        current_content += text
                        event_data["choices"][0]["delta"] = {"content": text}
                        
                    if "reasoningContent" in response["data"]["delta"]:
                        if 'text' in response["data"]["delta"]["reasoningContent"]:
                            if not thinking_start:
                                text = "<thinking>" + response["data"]["delta"]["reasoningContent"]["text"]
                                thinking_start = True
                            else:
                                text = response["data"]["delta"]["reasoningContent"]["text"]
                            event_data["choices"][0]["delta"] = {"content": text}
                            thinking_text_index += 1

                elif response["type"] == "block_stop":
                    if tooluse_start:
                        text =  "</tool_input>"
                        current_content += text
                        tooluse_start = False
                        event_data["choices"][0]["delta"] = {"content": text}
                        
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
                    yield "data: [DONE]\n\n"
                    break
                    
            elif isinstance(item, str):  # 来自心跳的消息
                yield item
            

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
        # 停止心跳任务
        heartbeat_stop_event.set()
        
        # save history message 
        await session.chat_client.save_history()
        # 清除活跃流列表中的请求
        try:
            if stream_id:
                # 清理同步：先从ChatClientStream中删除，再从active_streams中删除
                session.chat_client.unregister_stream(stream_id)
                await delete_stream_id(stream_id)
                logger.info(f"Stream {stream_id} unregistered")
        except Exception as e:
            logger.error(f"Error cleaning up stream {stream_id}: {e}")


async def _merge_streams(*streams):
    """合并多个异步生成器流"""
    import asyncio
    from collections import deque
    
    # 创建队列来存储每个流的状态
    stream_tasks = []
    for stream in streams:
        stream_iter = aiter(stream)
        task = asyncio.create_task(anext(stream_iter, StopAsyncIteration))
        stream_tasks.append((task, stream_iter))
    
    try:
        while stream_tasks:
            # 等待任何一个流产生结果
            done, pending = await asyncio.wait(
                [task for task, _ in stream_tasks], 
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # 处理完成的任务
            new_stream_tasks = []
            for task, stream_iter in stream_tasks:
                if task in done:
                    try:
                        result = await task
                        if result is not StopAsyncIteration:
                            yield result
                            # 创建新任务来获取下一个值
                            new_task = asyncio.create_task(anext(stream_iter, StopAsyncIteration))
                            new_stream_tasks.append((new_task, stream_iter))
                        # 如果结果是 StopAsyncIteration，该流已结束，不重新添加
                    except StopAsyncIteration:
                        # 流已结束
                        pass
                    except Exception as e:
                        logger.error(f"Error in merged stream task: {e}")
                        # 取消所有正在运行和新添加的任务
                        for t, _ in stream_tasks:
                            if not t.done():
                                t.cancel()
                        for t, _ in new_stream_tasks:
                            if not t.done():
                                t.cancel()
                        # 把异常继续向外抛出
                        raise
            
                else:
                    # 任务仍在运行
                    new_stream_tasks.append((task, stream_iter))
                    
            stream_tasks = new_stream_tasks
            
    except Exception as e:
        logger.error(f"Error in _merge_streams: {e}")
        # 把异常继续向外抛出
        raise
    finally:
        # 清理所有剩余的任务
        for task, _ in stream_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

@app.post("/v1/chat/completions")
async def chat_completions(
    request: Request, 
    data: ChatCompletionRequest, 
    background_tasks: BackgroundTasks,
    auth: HTTPAuthorizationCredentials = Security(security)
):
    # 获取用户会话
    session = await get_or_create_user_session(request, auth)
    # 记录会话活动
    session.last_active = datetime.now()

    logger.info(f'keep_session:{data.keep_session}')

    if not data.messages:
        return JSONResponse(content=ChatResponse(
            id=f"chat{time.time_ns()}",
            model=data.model,
            created=int(time.time()),
            choices=[{
                "index": 0,
                "message": {"role": "assistant", "content": ""},
                "finish_reason": "load" 
            }],
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        ).model_dump())

    # 处理流式请求
    if data.stream:
        # 为流式请求生成唯一ID
        stream_id = f"stream_{session.user_id}_{time.time_ns()}"
        return StreamingResponse(
            stream_chat_response(data, session, stream_id),
            media_type="text/event-stream",
            headers={"X-Stream-ID": stream_id}  # 添加流ID到响应头，便于前端跟踪
        )
    else:
        logger.error(f"Only support stream")
        raise HTTPException(status_code=500, detail="Only support stream")


def generate_self_signed_cert(cert_dir='certificates'):
    """生成自签名证书用于HTTPS开发环境"""
    import subprocess
    
    # 创建证书目录
    if not os.path.exists(cert_dir):
        os.makedirs(cert_dir, exist_ok=True)
        logger.info(f"创建证书目录: {cert_dir}")
    
    key_path = os.path.join(cert_dir, 'localhost.key')
    cert_path = os.path.join(cert_dir, 'localhost.crt')
    
    # 检查证书是否已存在
    if os.path.exists(key_path) and os.path.exists(cert_path):
        logger.info("证书已存在，将使用现有证书")
        return key_path, cert_path
    
    # 生成新的私钥和证书
    logger.info("正在为localhost生成自签名证书...")
    try:
        subprocess.run([
            'openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
            '-sha256', '-days', '365', '-subj', '/CN=localhost',
            '-keyout', key_path, '-out', cert_path
        ], check=True)
        
        logger.info(f"证书生成成功! 私钥: {key_path}, 证书: {cert_path}")
        return key_path, cert_path
    except subprocess.CalledProcessError as e:
        logger.error(f"生成证书时出错: {e}")
        return None, None
    except FileNotFoundError:
        logger.error("未找到OpenSSL。请安装OpenSSL以生成证书。")
        return None, None

if __name__ == '__main__':
    import uvicorn
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=7002)
    parser.add_argument('--mcp-conf', default='', help="the mcp servers json config file")
    parser.add_argument('--user-conf', default='conf/user_mcp_configs.json',
                       help="用户MCP服务器配置文件路径")
    parser.add_argument('--https', action='store_true', help="启用HTTPS")
    parser.add_argument('--cert-dir', default='certificates', help="证书目录")
    parser.add_argument('--ssl-keyfile', default='', help="SSL密钥文件路径")
    parser.add_argument('--ssl-certfile', default='', help="SSL证书文件路径")
    args = parser.parse_args()
    
    # 设置用户配置文件路径环境变量
    os.environ['USER_MCP_CONFIG_FILE'] = args.user_conf
    
    try:
        loop = asyncio.new_event_loop()

        if args.mcp_conf:
            with open(args.mcp_conf, 'r') as f:
                conf = json.load(f)
                # 加载全局MCP服务器配置
                for server_id, server_conf in conf.get('mcpServers', {}).items():
                    if server_conf.get('status') == 0:
                        continue
                    shared_mcp_server_list[server_id] = server_conf.get('description', server_id)
                    save_global_server_config(server_id, server_conf)

                # 加载模型配置
                for model_conf in conf.get('models', []):
                    llm_model_list[model_conf['model_id']] = model_conf['model_name']
        
        # 配置HTTPS
        ssl_keyfile = None
        ssl_certfile = None
        
        if args.https:
            if args.ssl_keyfile and args.ssl_certfile:
                ssl_keyfile = args.ssl_keyfile
                ssl_certfile = args.ssl_certfile
                logger.info(f"使用指定的SSL证书: {ssl_certfile} 和密钥: {ssl_keyfile}")
            else:
                ssl_keyfile, ssl_certfile = generate_self_signed_cert(args.cert_dir)
                if not ssl_keyfile or not ssl_certfile:
                    logger.warning("无法生成SSL证书，将使用HTTP而非HTTPS")
        
        # 配置uvicorn
        config_kwargs = {
            "app": app,
            "host": args.host,
            "port": args.port,
            "loop": loop,
            "timeout_keep_alive": 3600,  # 设置为1小时或更长
            "limit_concurrency": 100,  # 限制并发连接数
            "limit_max_requests": 1000,  # 限制最大请求数
            "timeout_graceful_shutdown": 30  # 优雅关闭超时
        }
        
        # 如果启用HTTPS且有有效证书，添加SSL配置
        if args.https and ssl_keyfile and ssl_certfile:
            config_kwargs["ssl_keyfile"] = ssl_keyfile
            config_kwargs["ssl_certfile"] = ssl_certfile
            logger.info(f"启用HTTPS，服务器将在 https://{args.host}:{args.port} 上运行")
        else:
            logger.info(f"使用HTTP，服务器将在 http://{args.host}:{args.port} 上运行")
        
        config = uvicorn.Config(**config_kwargs)
        server = uvicorn.Server(config)
        loop.run_until_complete(server.serve())
    finally:
        # 确保退出时清理资源并保存用户配置
        cleanup_tasks = []
        for user_id, session in user_sessions.items():
            cleanup_tasks.append(session.cleanup())
        
        if cleanup_tasks:
            loop.run_until_complete(asyncio.gather(*cleanup_tasks))
        loop.close()
