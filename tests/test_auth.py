"""
Unit tests for src/auth.py (Cognito access-token verification).

Run: uv run --with pytest pytest tests/test_auth.py
"""
import asyncio
import os
import sys
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import auth  # noqa: E402

POOL_ID = "us-east-1_TestPool"
CLIENT_ID = "test-client-id"
ISSUER = f"https://cognito-idp.us-east-1.amazonaws.com/{POOL_ID}"

_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class _FakeSigningKey:
    def __init__(self, key):
        self.key = key


class _FakeJWKClient:
    def get_signing_key_from_jwt(self, token):
        return _FakeSigningKey(_key.public_key())


@pytest.fixture(autouse=True)
def cognito_env(monkeypatch):
    monkeypatch.setenv("COGNITO_USER_POOL_ID", POOL_ID)
    monkeypatch.setenv("COGNITO_APP_CLIENT_ID", CLIENT_ID)
    auth._get_verifier.cache_clear()
    verifier = auth.get_verifier()
    monkeypatch.setattr(verifier, "_jwks_client", _FakeJWKClient())
    yield
    auth._get_verifier.cache_clear()


def _token(key=_key, **overrides):
    now = int(time.time())
    claims = {
        "sub": "11111111-2222-3333-4444-555555555555",
        "username": "alice",
        "iss": ISSUER,
        "client_id": CLIENT_ID,
        "token_use": "access",
        "iat": now,
        "exp": now + 3600,
    }
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test"})


def _auth(token):
    return asyncio.run(auth.authenticate(
        HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)))


def _status(token):
    with pytest.raises(HTTPException) as e:
        _auth(token)
    return e.value.status_code


def test_valid_token_returns_sub():
    user = _auth(_token())
    assert user.user_id == "11111111-2222-3333-4444-555555555555"
    assert user.username == "alice"


def test_missing_credentials_rejected():
    with pytest.raises(HTTPException) as e:
        asyncio.run(auth.authenticate(None))
    assert e.value.status_code == 401


@pytest.mark.parametrize("token", [
    "not-a-jwt",
    "123456",  # the old shared API key no longer authenticates anyone
])
def test_garbage_rejected(token):
    assert _status(token) == 401


def test_wrong_signature_rejected():
    assert _status(_token(key=_other_key)) == 401


def test_expired_rejected():
    assert _status(_token(exp=int(time.time()) - 10)) == 401


def test_wrong_issuer_rejected():
    assert _status(_token(iss="https://cognito-idp.us-east-1.amazonaws.com/us-east-1_Other")) == 401


def test_wrong_client_rejected():
    assert _status(_token(client_id="another-client")) == 401


def test_id_token_rejected():
    assert _status(_token(token_use="id")) == 401


def test_missing_sub_rejected():
    assert _status(_token(sub=None)) == 401


def test_alg_none_rejected():
    claims = jwt.decode(_token(), options={"verify_signature": False})
    unsigned = jwt.encode(claims, key=None, algorithm="none")
    assert _status(unsigned) == 401


def test_not_configured_fails_closed(monkeypatch):
    monkeypatch.delenv("COGNITO_USER_POOL_ID")
    auth._get_verifier.cache_clear()
    assert _status(_token()) == 503
