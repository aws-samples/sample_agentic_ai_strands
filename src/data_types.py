"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
SPDX-License-Identifier: MIT-0
"""
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Literal, AsyncGenerator, Union
from pydantic import BaseModel, Field
       
class TextContent(BaseModel):
    type: Literal["text"] = "text"
    text: str

class ImageUrl(BaseModel):
    url: str
    detail: Optional[str] = "auto"

class ImageUrlContent(BaseModel):
    type: Literal["image_url"] = "image_url"
    image_url: ImageUrl

class FileObject(BaseModel):
    file_id: Optional[str] = None
    file_data: Optional[str] = None
    filename: Optional[str] = None

class FileContent(BaseModel):
    type: Literal["file"] = "file"
    file: FileObject

# Content can be either text, image_url, or file
ContentPart = Union[TextContent, ImageUrlContent, FileContent]

class Message(BaseModel):
    role: str
    content: Union[str, List[ContentPart]]

class ChatCompletionRequest(BaseModel):
    messages: List[Message]
    model: str
    max_tokens: int = 4000
    temperature: float = 0.5
    top_p: float = 0.9
    top_k: int = 250
    extra_params : Optional[dict] = {}
    stream: Optional[bool] = True
    tools: Optional[List[dict]] = []
    options: Optional[dict] = {}
    keep_session: Optional[bool] = False
    mcp_server_ids: Optional[List[str]] = []
    stream_id: Optional[str] = "default-stream-id"
    token:Optional[str] = None

class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Dict[str, int]
    
class StopStreamRequest(BaseModel):
    stream_id: str = ''
    
class AddMCPServerRequest(BaseModel):
    server_id: str = ''
    server_desc: str = ''
    command: Literal["npx", "uvx", "node", "python","docker","uv"] = Field(default='npx')
    args: List[str] = []
    env: Optional[Dict[str, str]] = Field(default_factory=dict) 
    config_json: Dict[str,Any] = Field(default_factory=dict)
    
class AddMCPServerResponse(BaseModel):
    errno: int
    msg: str = "ok"
    data: Dict[str, Any] = Field(default_factory=dict)
    
class OperationsRequest(BaseModel):
    user_id:str
    request_type: Literal["chatcompletion",'stopstream','removehistory']
    data: Union[StopStreamRequest,ChatCompletionRequest]