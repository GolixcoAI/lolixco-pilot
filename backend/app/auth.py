"""Supabase JWT authentication dependency.

Validates Supabase-issued Bearer tokens using:
1. Asymmetric verification via Supabase JWKS endpoint (RS256, ES256, PS256).
2. Symmetric verification via SUPABASE_JWT_SECRET (HS256).

Validates signature, expiration, audience ('authenticated'), optional issuer,
and subject UUID. Never decodes unverified JWT claims or logs tokens.
"""

import uuid
from dataclasses import dataclass
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from jwt.types import Options

from app.config import Settings, get_settings

security = HTTPBearer(auto_error=False)

_jwks_clients: dict[str, PyJWKClient] = {}


def get_jwks_client(jwks_url: str) -> PyJWKClient:
    """Return a cached PyJWKClient for the given JWKS URL."""
    if jwks_url not in _jwks_clients:
        _jwks_clients[jwks_url] = PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=3600)
    return _jwks_clients[jwks_url]


@dataclass(frozen=True)
class AuthenticatedUser:
    """Represents a verified user session."""

    user_id: str
    is_anonymous: bool = True
    role: str = "authenticated"
    access_token: str = ""


def verify_supabase_jwt(
    token: str,
    settings: Settings,
    jwks_client: Any | None = None,
) -> AuthenticatedUser:
    """Verify Supabase JWT token and extract user claims.

    Supports:
    - Asymmetric verification via Supabase JWKS (RS256, ES256, PS256)
    - Symmetric verification via SUPABASE_JWT_SECRET (HS256)

    Raises HTTPException(401) on missing credentials, signature failure,
    expired tokens, audience mismatch, or invalid subject claims.
    Never trusts unverified JWT claims.
    """
    if not token or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    clean_token = token.strip()

    # Raw non-JWT test identifiers (e.g. direct UUID) are NEVER permitted in production.
    # In development they are disabled by default, and only accepted if ALLOW_DEV_TEST_AUTH is True.
    # They remain supported in the isolated "test" environment for unit tests.
    # Any token with JWT structure (header.payload.sig) MUST be verified cryptographically.
    allow_test_shortcut = settings.APP_ENV == "test" or (
        settings.APP_ENV == "development" and getattr(settings, "ALLOW_DEV_TEST_AUTH", False)
    )
    if allow_test_shortcut and clean_token.count(".") != 2:
        candidate_uuid = clean_token.replace("test-user-", "").replace("anon-", "")
        try:
            val = str(uuid.UUID(candidate_uuid))
            return AuthenticatedUser(
                user_id=val,
                is_anonymous=True,
                role="authenticated",
                access_token=clean_token,
            )
        except ValueError:
            val = str(uuid.uuid5(uuid.NAMESPACE_DNS, clean_token))
            return AuthenticatedUser(
                user_id=val,
                is_anonymous=True,
                role="authenticated",
                access_token=clean_token,
            )

    # Inspect JWT header to determine signing algorithm
    try:
        header = jwt.get_unverified_header(clean_token)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Malformed JWT header: {type(exc).__name__}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    alg = header.get("alg")
    if not alg:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing 'alg' header in authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expected_aud = settings.SUPABASE_JWT_AUDIENCE or "authenticated"
    expected_iss = settings.SUPABASE_JWT_ISSUER if settings.SUPABASE_JWT_ISSUER else None

    decode_options: Options = {
        "verify_signature": True,
        "verify_aud": True,
        "verify_exp": True,
    }
    if expected_iss:
        decode_options["verify_iss"] = True

    payload: dict[str, Any]

    # Asymmetric verification (RS256, ES256, PS256) via JWKS
    if alg in ("RS256", "ES256", "PS256"):
        jwks_url = settings.SUPABASE_JWKS_URL or (
            f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
            if settings.SUPABASE_URL
            else ""
        )
        if not jwks_url and jwks_client is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Asymmetric token received but Supabase JWKS URL is not configured",
                headers={"WWW-Authenticate": "Bearer"},
            )

        client = jwks_client or get_jwks_client(jwks_url)
        try:
            signing_key = client.get_signing_key_from_jwt(clean_token)
            key_for_decode = signing_key.key
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Unable to retrieve signing key from Supabase JWKS: {type(exc).__name__}",
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            payload = jwt.decode(
                clean_token,
                key_for_decode,
                algorithms=[alg],
                audience=expected_aud,
                issuer=expected_iss,
                options=decode_options,
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidAudienceError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token audience verification failed",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidIssuerError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token issuer verification failed",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.PyJWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token verification failed: {type(exc).__name__}",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Symmetric verification (HS256) via SUPABASE_JWT_SECRET
    elif alg == "HS256":
        if not settings.SUPABASE_JWT_SECRET:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Symmetric HS256 token received but SUPABASE_JWT_SECRET is not configured",
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            payload = jwt.decode(
                clean_token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience=expected_aud,
                issuer=expected_iss,
                options=decode_options,
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidAudienceError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token audience verification failed",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidIssuerError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token issuer verification failed",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.PyJWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token verification failed: {type(exc).__name__}",
                headers={"WWW-Authenticate": "Bearer"},
            )

    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Unsupported token algorithm: '{alg}'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate subject (sub) claim
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload: missing subject claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_uuid = str(uuid.UUID(str(sub)))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: subject must be a valid UUID",
            headers={"WWW-Authenticate": "Bearer"},
        )

    is_anonymous = bool(
        payload.get("is_anonymous", False)
        or payload.get("app_metadata", {}).get("provider") == "anonymous"
    )
    role = str(payload.get("role", "authenticated"))

    return AuthenticatedUser(
        user_id=user_uuid,
        is_anonymous=is_anonymous,
        role=role,
        access_token=clean_token,
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    """FastAPI dependency to retrieve authenticated user from Authorization header."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header with Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_supabase_jwt(credentials.credentials, settings)
