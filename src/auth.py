"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
SPDX-License-Identifier: MIT-0

Amazon Cognito user authentication for the FastAPI backend.

Every request must carry a Cognito User Pool *access token* in the
``Authorization: Bearer <token>`` header. The token signature is verified
against the user pool's JWKS, and the caller's identity is taken from the
verified ``sub`` claim. Client-supplied identity headers (e.g. ``X-User-ID``)
are never trusted.

Required environment variables:
    COGNITO_USER_POOL_ID   e.g. us-east-1_AbCdEf123
    COGNITO_APP_CLIENT_ID  the app client the frontend signs in with

If either variable is missing, every request is rejected (fail closed).
"""
import asyncio
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

import jwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str           # Cognito `sub` claim, immutable per user
    username: Optional[str]


class CognitoTokenVerifier:
    def __init__(self, user_pool_id: str, app_client_id: str):
        # Pool IDs look like "<region>_<id>", e.g. us-east-1_AbCdEf123.
        region = user_pool_id.split("_", 1)[0]
        self.issuer = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
        self.app_client_id = app_client_id
        self._jwks_client = jwt.PyJWKClient(
            f"{self.issuer}/.well-known/jwks.json", cache_keys=True, lifespan=3600
        )

    def verify(self, token: str) -> AuthenticatedUser:
        """Verify a Cognito access token. Raises jwt.PyJWTError on any failure."""
        signing_key = self._jwks_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=self.issuer,
            options={"require": ["exp", "iat", "iss", "sub", "token_use", "client_id"]},
        )
        if claims.get("token_use") != "access":
            raise jwt.InvalidTokenError("token_use must be 'access'")
        if claims.get("client_id") != self.app_client_id:
            raise jwt.InvalidTokenError("token was issued for a different app client")
        return AuthenticatedUser(user_id=claims["sub"], username=claims.get("username"))


@lru_cache(maxsize=1)
def _get_verifier(user_pool_id: str, app_client_id: str) -> CognitoTokenVerifier:
    return CognitoTokenVerifier(user_pool_id, app_client_id)


def get_verifier() -> Optional[CognitoTokenVerifier]:
    user_pool_id = os.environ.get("COGNITO_USER_POOL_ID", "").strip()
    app_client_id = os.environ.get("COGNITO_APP_CLIENT_ID", "").strip()
    if not user_pool_id or not app_client_id:
        return None
    return _get_verifier(user_pool_id, app_client_id)


_UNAUTHORIZED_HEADERS = {"WWW-Authenticate": "Bearer"}


async def authenticate(auth: Optional[HTTPAuthorizationCredentials]) -> AuthenticatedUser:
    """Return the verified user for the request, or raise HTTP 401/503."""
    verifier = get_verifier()
    if verifier is None:
        logger.error("COGNITO_USER_POOL_ID / COGNITO_APP_CLIENT_ID not set; rejecting request")
        raise HTTPException(status_code=503, detail="Authentication is not configured")
    if auth is None or auth.scheme.lower() != "bearer" or not auth.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated",
                            headers=_UNAUTHORIZED_HEADERS)
    try:
        # PyJWKClient may fetch the JWKS over the network; keep it off the event loop.
        return await asyncio.to_thread(verifier.verify, auth.credentials)
    except jwt.PyJWTError as e:
        logger.warning(f"Rejected access token: {type(e).__name__}: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token",
                            headers=_UNAUTHORIZED_HEADERS)


async def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> AuthenticatedUser:
    """FastAPI dependency: the authenticated caller."""
    return await authenticate(auth)
