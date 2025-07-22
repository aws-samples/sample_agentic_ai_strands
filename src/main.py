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
from botocore.config import Config
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
                    session_lock,
                    DDB_TABLE,
                    generate_id_from_string,
                    save_user_server_config)
from agentcore_wrapper import invoke_agentcore_runtime
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
import boto3
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
)
# Initialize logger
logger = logging.getLogger(__name__)


# 全局模型和服务器配置
load_dotenv()  # load env vars from .env

llm_model_list = {}

API_KEY = os.environ.get("API_KEY")

security = HTTPBearer()


async def get_api_key(auth: HTTPAuthorizationCredentials = Security(security)):
    if auth.credentials == API_KEY:
        return auth.credentials
    raise HTTPException(status_code=403, detail="Could not validate credentials")



@asynccontextmanager
async def lifespan(app: FastAPI):
    """服务器启动时执行的任务"""
    # 启动其他初始化任务
    yield


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
    user_id = request.headers.get("X-User-ID", auth.credentials)
    server_configs = await get_user_server_configs(user_id)
    return JSONResponse(content={"servers": [{
        "server_id": sid, 
        "server_name": sid} for sid in server_configs.keys()]})

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
    
    logger.info(f"remove history for user:{user_id}")
    # 直接从ddb里删除记录即可
    await delete_user_message(user_id)
    # runtime_id = generate_id_from_string(user_id)
    
    # payload = {
    #     "user_id":user_id,
    #     "request_type":"removehistory"
    # }
    
    # response = invoke_agentcore_runtime(session_id=runtime_id,payload=payload)
    
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
    # 获取用户会话
    user_id = request.headers.get("X-User-ID", auth.credentials)
    logger.info(f"stopping request for user:{user_id} /{stream_id}")
    runtime_id = generate_id_from_string(user_id)
    
    payload = {
        "user_id":user_id,
        "request_type":"stopstream",
        "data":{"stream_id":stream_id}
    }
    
    response = invoke_agentcore_runtime(session_id=runtime_id,payload=payload)
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

    
    # 尝试从请求头获取用户ID，如果不存在则使用API密钥作为备用ID
    user_id = request.headers.get("X-User-ID", auth.credentials)
    
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
     # 保存用户服务器配置
    server_config = {
        "url":server_url,
        "command": server_cmd,
        "args": server_script_args,
        "env": server_script_envs,
        "description": server_desc,
        "token":token
    }
    ret = await save_user_server_config(user_id, server_id, server_config)
    if ret:
        return JSONResponse(content=AddMCPServerResponse(
            errno=0,
            msg="The server already been added!",
        ).model_dump())
    else:
        return JSONResponse(content=AddMCPServerResponse(
            errno=-1,
            msg=f"MCP server connect failed"
        ).model_dump())
    

@app.delete("/v1/remove/mcp_server/{server_id}")
async def remove_mcp_server(
    server_id: str,
    request: Request,
    auth: HTTPAuthorizationCredentials = Security(security)
):
    """删除用户的MCP服务器"""

    # 尝试从请求头获取用户ID，如果不存在则使用API密钥作为备用ID
    user_id = request.headers.get("X-User-ID", auth.credentials)
    # 从用户配置中删除
    await delete_user_server_config(user_id, server_id)
    logger.info(f"User {user_id} removed MCP server {server_id}")
    return JSONResponse(content=AddMCPServerResponse(
                errno=0,
                msg="Server removed successfully"
            ).model_dump())


async def _merge_streams(*streams):
    """合并多个异步生成器流，支持优雅停止和完整清理"""
    import asyncio
    
    # 创建队列来存储每个流的状态
    stream_tasks = []
    all_tasks = set()  # 跟踪所有创建的任务，确保完整清理
    
    try:
        # 初始化所有流的第一个任务
        for stream in streams:
            stream_iter = aiter(stream)
            task = asyncio.create_task(anext(stream_iter, StopAsyncIteration))
            stream_tasks.append((task, stream_iter))
            all_tasks.add(task)
        
        while stream_tasks:
            # 等待任何一个流产生结果，使用较短的超时时间以便更快响应停止信号
            done, pending = await asyncio.wait(
                [task for task, _ in stream_tasks],
                return_when=asyncio.FIRST_COMPLETED,
                timeout=0.5  # 适中的超时时间，平衡响应性和CPU使用
            )
            
            # 处理完成的任务
            new_stream_tasks = []
            main_stream_ended = False
            
            for task, stream_iter in stream_tasks:
                if task in done:
                    try:
                        result = await task
                        if result is not StopAsyncIteration:
                            yield result
                            # 检查是否是主要流（agent stream）的真正结束信号
                            if result == "data: [DONE]":
                                main_stream_ended = True
                                logger.info("Main stream ended, stopping all streams")
                            else:
                                # 创建新任务来获取下一个值
                                new_task = asyncio.create_task(anext(stream_iter, StopAsyncIteration))
                                new_stream_tasks.append((new_task, stream_iter))
                                all_tasks.add(new_task)
                        # 如果结果是 StopAsyncIteration，该流已结束，不重新添加
                        else:
                            main_stream_ended = True
                    except StopAsyncIteration:
                        # 流已结束
                        logger.debug("Stream ended normally")
                    except asyncio.CancelledError:
                        # 任务被取消，正常退出
                        logger.debug("Stream task cancelled")
                        raise
                    except Exception as e:
                        logger.error(f"Error in merged stream task: {e}")
                        # 发生异常时立即停止所有流
                        main_stream_ended = True
                        break
                else:
                    # 任务仍在运行
                    new_stream_tasks.append((task, stream_iter))
                    
            stream_tasks = new_stream_tasks
            
            # 如果主要流已结束，立即退出循环
            if main_stream_ended:
                break
                
    except asyncio.CancelledError:
        logger.info("_merge_streams cancelled, cleaning up...")
        raise
    except Exception as e:
        logger.error(f"Error in _merge_streams: {e}")
        raise
    finally:
        # 完整清理所有任务
        logger.debug("Cleaning up all stream tasks...")
        cleanup_tasks = []
        
        # 取消所有未完成的任务
        for task in all_tasks:
            if not task.done():
                task.cancel()
                cleanup_tasks.append(task)
        
        # 等待所有被取消的任务完成清理
        if cleanup_tasks:
            try:
                await asyncio.gather(*cleanup_tasks, return_exceptions=True)
            except Exception as e:
                logger.error(f"Error during task cleanup: {e}")
        
        logger.debug(f"Cleaned up {len(cleanup_tasks)} stream tasks")
            
async def process_query_stream(boto3_response) -> AsyncGenerator[str, None]:
    if "text/event-stream" in boto3_response.get("contentType", ""):
        for line in boto3_response["response"].iter_lines(chunk_size=1):
            if line:
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    line = json.loads(line[6:])
                    yield line
    
async def stream_chat_response(data: ChatCompletionRequest, user_id: str, stream_id: str = None) -> AsyncGenerator[str, None]:
    """为特定用户生成流式聊天响应"""    
    # 尝试从请求头获取用户ID，如果不存在则使用API密钥作为备用ID
    runtime_id = generate_id_from_string(user_id)
    
    payload = {
        "user_id":user_id,
        "request_type":"chatcompletion",
        "data" :{**data.model_dump(),"stream_id":stream_id}
    }
    
    logger.info(f"runtimesid:{runtime_id}\npayload:{payload}")
    
        # 心跳任务控制
    heartbeat_task = None
    heartbeat_stop_event = asyncio.Event()
    
    async def heartbeat_sender():
        """独立的心跳发送任务"""
        try:
            while not heartbeat_stop_event.is_set():
                await asyncio.sleep(10)  # 每10秒发送一次心跳，减少频率
                if not heartbeat_stop_event.is_set():
                    logger.info("sse heartbeat")  # 改为debug级别，减少日志噪音
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
    
    try:        
        boto3_response = invoke_agentcore_runtime(session_id=runtime_id,payload=payload)
        # 创建心跳生成器
        heartbeat_gen = heartbeat_sender()
        
        response_stream = process_query_stream(boto3_response)
        # 使用合并流来处理响应和心跳
        async for item in _merge_streams(response_stream, heartbeat_gen):
            yield item
            

    except Exception as e:
        logger.error(f"Stream error for user {user_id}: {e}",exc_info=True)
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
        
            
    
    
@app.post("/v1/chat/completions")
async def chat_completions(
    request: Request, 
    data: ChatCompletionRequest, 
    background_tasks: BackgroundTasks,
    auth: HTTPAuthorizationCredentials = Security(security)
):

    user_id = request.headers.get("X-User-ID", auth.credentials)

    # 处理流式请求
    if data.stream:
        # 为流式请求生成唯一ID
        stream_id = f"stream_{user_id}_{time.time_ns()}"
        return StreamingResponse(
            stream_chat_response(data, user_id, stream_id),
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
        loop.close()
