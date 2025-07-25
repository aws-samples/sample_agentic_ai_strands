"""
AWS Cognito JWT Token Authentication
"""
import os
import json
import boto3
import logging
from typing import Dict, Optional, Union
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt.exceptions import InvalidTokenError
import requests
from functools import lru_cache

logger = logging.getLogger(__name__)

# # Configuration
API_KEY = os.environ.get("API_KEY", "123456")
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID", "")
COGNITO_CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID", "")

security = HTTPBearer()

def get_cognito_region():
    if COGNITO_USER_POOL_ID:
        # Extract region from UserPool ID format: us-west-2_xxxxxxxxx
        region_part = COGNITO_USER_POOL_ID.split('_')[0]
        if region_part and len(region_part.split('-')) >= 3:
            return region_part
    return os.environ.get("AWS_REGION", "us-west-2")

COGNITO_REGION = get_cognito_region()

def verify_cognito_jwt(token: str) -> Optional[Dict]:
    """验证 Cognito JWT token - 简化版本，不验证签名"""
    try:
        # 如果没有配置 Cognito 信息，直接返回 None
        if not COGNITO_USER_POOL_ID or not COGNITO_CLIENT_ID:
            return None
        
        # 先解码不验证签名，获取基本信息
        payload = jwt.decode(
            token,
            options={"verify_signature": False}
        )
        
        # 基本验证
        if payload.get('client_id') != COGNITO_CLIENT_ID:
            logger.warning(f"Token client_id mismatch: {payload.get('client_id')} != {COGNITO_CLIENT_ID}")
            return None
        
        expected_issuer = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}"
        if payload.get('iss') != expected_issuer:
            logger.warning(f"Token issuer mismatch: {payload.get('iss')} != {expected_issuer}")
            return None
        
        # 检查token类型
        if payload.get('token_use') != 'access':
            logger.warning(f"Invalid token_use: {payload.get('token_use')}")
            return None
        
        # 检查过期时间
        import time
        if payload.get('exp', 0) < time.time():
            logger.warning("Token expired")
            return None
        
        return payload
    
    except InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {e}")
        return None
    except Exception as e:
        logger.error(f"Error verifying JWT token: {e}")
        return None

def extract_user_info(jwt_payload: Dict) -> Dict:
    """从 JWT payload 中提取用户信息"""
    return {
        'user_id': jwt_payload.get('sub'),
        'username': jwt_payload.get('cognito:username'),
        'email': jwt_payload.get('email'),
        'token_use': jwt_payload.get('token_use'),
        'exp': jwt_payload.get('exp'),
        'iat': jwt_payload.get('iat'),
        'client_id': jwt_payload.get('client_id')
    }

class AuthResult:
    """认证结果类"""
    def __init__(self, user_id: str, username: Optional[str] = None, email: Optional[str] = None, auth_type: str = 'api_key'):
        self.user_id = user_id
        self.username = username
        self.email = email
        self.auth_type = auth_type  # 'jwt' or 'api_key'

async def authenticate_user(auth: HTTPAuthorizationCredentials = Security(security)) -> AuthResult:
    """
    统一认证函数，支持 JWT token 和 API Key 两种认证方式
    """
    token = auth.credentials
    
    # 首先尝试验证 JWT token
    if COGNITO_USER_POOL_ID:
        jwt_payload = verify_cognito_jwt(token)
        if jwt_payload:
            user_info = extract_user_info(jwt_payload)
            logger.info(f"JWT authentication successful for user: {user_info['username']}")
            return AuthResult(
                user_id=user_info['user_id'],
                username=user_info['username'],
                email=user_info['email'],
                auth_type='jwt'
            )
    if token == API_KEY:
        logger.info(f"API key authentication successful for development mode")
        return AuthResult(
            user_id='dev',
            username='dev',
            email='dev@dev.com',
            auth_type='api_key'
        )
        
    
    # 两种认证方式都失败
    logger.warning(f"Authentication failed for token: {token[:20]}...")
    raise HTTPException(
        status_code=401,
        detail="Invalid authentication credentials"
    )

# 兼容性函数，保持与原有代码的兼容性
async def get_api_key(auth: HTTPAuthorizationCredentials = Security(security)) -> str:
    """
    兼容性函数，用于不需要详细用户信息的场景
    """
    auth_result = await authenticate_user(auth)
    return auth_result.user_id

def get_user_id_from_request(request, auth_result: AuthResult) -> str:
    """
    从请求中获取用户ID，优先级：X-User-ID header > JWT payload > auth credentials
    """
    # 首先检查请求头中的 X-User-ID
    user_id_header = request.headers.get("X-User-ID")
    if user_id_header:
        return user_id_header
    
    # 如果是 JWT 认证，使用 JWT 中的用户ID
    if auth_result.auth_type == 'jwt':
        return auth_result.user_id
    
    # 否则使用认证凭据
    return auth_result.user_id