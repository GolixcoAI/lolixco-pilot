"""Tests for Supabase JWT verification, JWKS asymmetric keys, and security claims."""

import time
import uuid
from unittest.mock import MagicMock

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from app.auth import AuthenticatedUser, verify_supabase_jwt
from app.config import Settings


def generate_test_hs256_jwt(
    secret: str,
    user_id: str,
    role: str = "authenticated",
    aud: str = "authenticated",
    iss: str | None = None,
    exp_offset: int = 3600,
    is_anonymous: bool = True,
) -> str:
    """Helper to mint test HS256 Supabase JWTs."""
    now = int(time.time())
    payload = {
        "sub": user_id,
        "role": role,
        "aud": aud,
        "iat": now,
        "exp": now + exp_offset,
        "is_anonymous": is_anonymous,
    }
    if iss:
        payload["iss"] = iss
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
def rsa_keypair() -> tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey, bytes]:
    """Generate ephemeral RSA keypair for testing asymmetric JWKS verification."""
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = priv.public_key()
    pem_priv = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return priv, pub, pem_priv


def test_verify_jwt_valid_hs256_signature() -> None:
    secret = "super-secret-supabase-jwt-key-32chars"
    user_id = str(uuid.uuid4())
    token = generate_test_hs256_jwt(secret=secret, user_id=user_id)
    settings = Settings(SUPABASE_JWT_SECRET=secret)

    user = verify_supabase_jwt(token, settings)
    assert isinstance(user, AuthenticatedUser)
    assert user.user_id == user_id
    assert user.is_anonymous is True


def test_verify_jwt_invalid_hs256_signature() -> None:
    secret_real = "super-secret-supabase-jwt-key-32chars"
    secret_wrong = "wrong-secret-key-different-for-fail"
    user_id = str(uuid.uuid4())
    token = generate_test_hs256_jwt(secret=secret_wrong, user_id=user_id)
    settings = Settings(SUPABASE_JWT_SECRET=secret_real)

    with pytest.raises(HTTPException) as exc:
        verify_supabase_jwt(token, settings)
    assert exc.value.status_code == 401
    assert "Token verification failed" in exc.value.detail


def test_verify_jwt_expired_hs256() -> None:
    secret = "super-secret-supabase-jwt-key-32chars"
    user_id = str(uuid.uuid4())
    token = generate_test_hs256_jwt(secret=secret, user_id=user_id, exp_offset=-10)
    settings = Settings(SUPABASE_JWT_SECRET=secret)

    with pytest.raises(HTTPException) as exc:
        verify_supabase_jwt(token, settings)
    assert exc.value.status_code == 401
    assert "expired" in exc.value.detail.lower()


def test_verify_jwt_missing_hs256_secret_raises() -> None:
    secret = "super-secret-supabase-jwt-key-32chars"
    user_id = str(uuid.uuid4())
    token = generate_test_hs256_jwt(secret=secret, user_id=user_id)
    settings = Settings(SUPABASE_JWT_SECRET="")

    with pytest.raises(HTTPException) as exc:
        verify_supabase_jwt(token, settings)
    assert exc.value.status_code == 401
    assert "SUPABASE_JWT_SECRET is not configured" in exc.value.detail


def test_verify_jwt_valid_rs256_jwks(
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey, bytes],
) -> None:
    _, pub, pem_priv = rsa_keypair
    user_id = str(uuid.uuid4())
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": user_id,
            "aud": "authenticated",
            "role": "authenticated",
            "iat": now,
            "exp": now + 3600,
            "is_anonymous": False,
        },
        pem_priv,
        algorithm="RS256",
        headers={"kid": "mock-key-1"},
    )

    mock_client = MagicMock()
    mock_key = MagicMock()
    mock_key.key = pub
    mock_client.get_signing_key_from_jwt.return_value = mock_key

    settings = Settings(SUPABASE_URL="https://myproject.supabase.co")
    user = verify_supabase_jwt(token, settings, jwks_client=mock_client)

    assert isinstance(user, AuthenticatedUser)
    assert user.user_id == user_id
    assert user.is_anonymous is False


def test_verify_jwt_invalid_rs256_signature(
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey, bytes],
) -> None:
    _, _, pem_priv = rsa_keypair
    # Generate a different keypair for verification
    wrong_priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    wrong_pub = wrong_priv.public_key()

    user_id = str(uuid.uuid4())
    token = jwt.encode(
        {"sub": user_id, "aud": "authenticated", "exp": int(time.time()) + 3600},
        pem_priv,
        algorithm="RS256",
        headers={"kid": "key1"},
    )

    mock_client = MagicMock()
    mock_key = MagicMock()
    mock_key.key = wrong_pub
    mock_client.get_signing_key_from_jwt.return_value = mock_key

    settings = Settings(SUPABASE_URL="https://myproject.supabase.co")
    with pytest.raises(HTTPException) as exc:
        verify_supabase_jwt(token, settings, jwks_client=mock_client)
    assert exc.value.status_code == 401
    assert "verification failed" in exc.value.detail.lower()


def test_verify_jwt_expired_rs256(
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey, bytes],
) -> None:
    _, pub, pem_priv = rsa_keypair
    user_id = str(uuid.uuid4())
    token = jwt.encode(
        {"sub": user_id, "aud": "authenticated", "exp": int(time.time()) - 100},
        pem_priv,
        algorithm="RS256",
        headers={"kid": "key1"},
    )

    mock_client = MagicMock()
    mock_key = MagicMock()
    mock_key.key = pub
    mock_client.get_signing_key_from_jwt.return_value = mock_key

    settings = Settings(SUPABASE_URL="https://myproject.supabase.co")
    with pytest.raises(HTTPException) as exc:
        verify_supabase_jwt(token, settings, jwks_client=mock_client)
    assert exc.value.status_code == 401
    assert "expired" in exc.value.detail.lower()


def test_verify_jwt_rs256_audience_mismatch(
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey, bytes],
) -> None:
    _, pub, pem_priv = rsa_keypair
    user_id = str(uuid.uuid4())
    token = jwt.encode(
        {"sub": user_id, "aud": "wrong-audience", "exp": int(time.time()) + 3600},
        pem_priv,
        algorithm="RS256",
        headers={"kid": "key1"},
    )

    mock_client = MagicMock()
    mock_key = MagicMock()
    mock_key.key = pub
    mock_client.get_signing_key_from_jwt.return_value = mock_key

    settings = Settings(
        SUPABASE_URL="https://myproject.supabase.co",
        SUPABASE_JWT_AUDIENCE="authenticated",
    )
    with pytest.raises(HTTPException) as exc:
        verify_supabase_jwt(token, settings, jwks_client=mock_client)
    assert exc.value.status_code == 401
    assert "audience verification failed" in exc.value.detail.lower()


def test_verify_jwt_rs256_issuer_validation(
    rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey, bytes],
) -> None:
    _, pub, pem_priv = rsa_keypair
    user_id = str(uuid.uuid4())
    token = jwt.encode(
        {
            "sub": user_id,
            "aud": "authenticated",
            "iss": "https://other.supabase.co/auth/v1",
            "exp": int(time.time()) + 3600,
        },
        pem_priv,
        algorithm="RS256",
        headers={"kid": "key1"},
    )

    mock_client = MagicMock()
    mock_key = MagicMock()
    mock_key.key = pub
    mock_client.get_signing_key_from_jwt.return_value = mock_key

    settings = Settings(
        SUPABASE_URL="https://myproject.supabase.co",
        SUPABASE_JWT_ISSUER="https://myproject.supabase.co/auth/v1",
    )
    with pytest.raises(HTTPException) as exc:
        verify_supabase_jwt(token, settings, jwks_client=mock_client)
    assert exc.value.status_code == 401
    assert "issuer verification failed" in exc.value.detail.lower()


def test_verify_jwt_unsupported_algorithm() -> None:
    user_id = str(uuid.uuid4())
    # Create token with 'none' alg
    token = jwt.encode({"sub": user_id, "aud": "authenticated"}, key="", algorithm="none")
    settings = Settings(SUPABASE_JWT_SECRET="secret")

    with pytest.raises(HTTPException) as exc:
        verify_supabase_jwt(token, settings)
    assert exc.value.status_code == 401
    assert "Unsupported token algorithm" in exc.value.detail


def test_verify_jwt_never_trusts_unverified_claims() -> None:
    # A forged 3-part token must not be accepted without valid signature
    forged_token = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiIxMjNlNDU2Ny1lODliLTEyZDMtYTQ1Ni00MjY2MTQxNzQwMDAifQ."
        "invalid_signature_bytes_here"
    )
    settings = Settings(SUPABASE_JWT_SECRET="correct-secret", APP_ENV="development")

    with pytest.raises(HTTPException) as exc:
        verify_supabase_jwt(forged_token, settings)
    assert exc.value.status_code == 401


def test_verify_jwt_missing_subject() -> None:
    secret = "super-secret-supabase-jwt-key-32chars"
    now = int(time.time())
    token = jwt.encode({"aud": "authenticated", "exp": now + 3600}, secret, algorithm="HS256")
    settings = Settings(SUPABASE_JWT_SECRET=secret)

    with pytest.raises(HTTPException) as exc:
        verify_supabase_jwt(token, settings)
    assert exc.value.status_code == 401
    assert "missing subject claim" in exc.value.detail.lower()


def test_verify_jwt_invalid_uuid() -> None:
    secret = "super-secret-supabase-jwt-key-32chars"
    token = generate_test_hs256_jwt(secret=secret, user_id="not-a-valid-uuid")
    settings = Settings(SUPABASE_JWT_SECRET=secret)

    with pytest.raises(HTTPException) as exc:
        verify_supabase_jwt(token, settings)
    assert exc.value.status_code == 401
    assert "valid uuid" in exc.value.detail.lower()


def test_verify_jwt_empty_token() -> None:
    settings = Settings(SUPABASE_JWT_SECRET="secret")
    with pytest.raises(HTTPException) as exc:
        verify_supabase_jwt("", settings)
    assert exc.value.status_code == 401


def test_verify_raw_dev_test_identifier_without_secret() -> None:
    user_id = str(uuid.uuid4())
    settings = Settings(SUPABASE_JWT_SECRET="", APP_ENV="test")
    user = verify_supabase_jwt(user_id, settings)
    assert user.user_id == user_id
