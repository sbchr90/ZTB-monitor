"""Authentication helpers for the ZTB API.

Flow:
  1. ZTB_API_KEY  →  POST /api/v3/api-key-auth/login  →  delegate_token (JWT)
  2. delegate_token is stored in .env as ZTB_BEARER_TOKEN
  3. All subsequent API calls use delegate_token in the 'authorization' header
  4. Before each run the token's JWT expiry claim is checked; if missing or
     expired a fresh login is performed automatically.
"""

import base64
import json
import os
import re
import time
from pathlib import Path

import requests

_LOGIN_PATH = "/api/v3/api-key-auth/login"
_EXPIRY_BUFFER = 60  # re-authenticate this many seconds before actual expiry


# ---------------------------------------------------------------------------
# JWT helpers (no third-party library required)
# ---------------------------------------------------------------------------

def _decode_jwt_payload(token: str) -> dict:
    """Decode the payload section of a JWT without verifying the signature."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        padding = "=" * (4 - len(parts[1]) % 4)
        decoded = base64.urlsafe_b64decode(parts[1] + padding)
        return json.loads(decoded)
    except Exception:
        return {}


def is_token_valid(token: str) -> bool:
    """Return True if token is non-empty and not within the expiry buffer.

    If the token is not a JWT (no 'exp' claim can be found) it is treated as
    a static token and considered valid as long as it is non-empty.
    """
    if not token:
        return False
    payload = _decode_jwt_payload(token)
    exp = payload.get("exp")
    if exp is None:
        # Not a JWT or no expiry claim — treat as always valid
        return True
    return time.time() < (exp - _EXPIRY_BUFFER)


# ---------------------------------------------------------------------------
# .env persistence
# ---------------------------------------------------------------------------

def _update_env_file(key: str, value: str, env_path: Path) -> None:
    """Write or update a single key=value line in the .env file."""
    content = env_path.read_text() if env_path.exists() else ""
    pattern = rf"^{re.escape(key)}=.*$"
    new_line = f"{key}={value}"
    if re.search(pattern, content, re.MULTILINE):
        content = re.sub(pattern, new_line, content, flags=re.MULTILINE)
    else:
        content = content.rstrip("\n") + f"\n{new_line}\n"
    env_path.write_text(content)


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def login(base_url: str, api_key: str, env_path: Path, timeout: int = 30) -> str:
    """Exchange the static API key for a delegate bearer token.

    Persists the new token to *env_path* and sets it in os.environ so the
    running process picks it up immediately without a restart.

    Returns the delegate_token string.
    """
    resp = requests.post(
        f"{base_url}{_LOGIN_PATH}",
        json={"api_key": api_key},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()

    token = (data.get("result") or {}).get("delegate_token", "")
    if not token:
        raise ValueError(f"Login succeeded but no delegate_token in response: {data}")

    _update_env_file("ZTB_BEARER_TOKEN", token, env_path)
    os.environ["ZTB_BEARER_TOKEN"] = token
    return token


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def ensure_token(base_url: str, api_key: str, bearer_token: str, env_path: Path, timeout: int = 30) -> str:
    """Return a valid bearer token, logging in first if necessary.

    Args:
        base_url:      API base URL.
        api_key:       Static ZTB API key (ZTB_API_KEY).
        bearer_token:  Current token from config / env (may be empty or expired).
        env_path:      Path to the .env file where the token is persisted.
        timeout:       HTTP timeout for the login request.

    Returns:
        A valid delegate bearer token.
    """
    if is_token_valid(bearer_token):
        return bearer_token

    print("[ztb-monitor] Bearer token missing or expired — authenticating...")
    token = login(base_url, api_key, env_path, timeout)
    print("[ztb-monitor] Authenticated successfully.")
    return token
