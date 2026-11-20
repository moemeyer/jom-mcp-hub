"""Bearer API key loading and verification for Justice Nexus MCP."""

from __future__ import annotations

import json
import logging
import os
import secrets
import sys
from pathlib import Path
from typing import Any

from fastmcp.server.auth import AccessToken, TokenVerifier
from google.api_core.exceptions import GoogleAPIError
from google.cloud import secretmanager

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from oauth.gcp_secret_resource import resolve_secret_version_resource_name

_LOG = logging.getLogger(__name__)

_API_KEY_ENV_VARS = ("MCP_API_KEY", "JUSTICE_NEXUS_MCP_API_KEY")
_DEFAULT_SECRET_PATH = "justice-nexus-mcp-api-key"
_JSON_KEY_CANDIDATES = ("mcp_api_key", "api_key", "token")


def _parse_secret_payload(raw: str) -> str:
    stripped = raw.strip()
    if not stripped:
        raise ValueError("Secret payload is empty")
    if stripped.startswith("{"):
        data: dict[str, Any] = json.loads(stripped)
        for key in _JSON_KEY_CANDIDATES:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        raise ValueError("Secret JSON missing mcp_api_key/api_key")
    return stripped


def load_mcp_api_key() -> str:
    """
    Load the MCP bearer token from environment or GCP Secret Manager.

    Never logs or returns the key to callers beyond server startup wiring.
    """
    for env_name in _API_KEY_ENV_VARS:
        value = os.environ.get(env_name, "").strip()
        if value:
            return value

    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "ghlpest-controlv2")
    secret_path = os.environ.get("JUSTICE_NEXUS_SECRET_PATH", _DEFAULT_SECRET_PATH).strip()
    secret_name = resolve_secret_version_resource_name(secret_path, project=project)

    try:
        client = secretmanager.SecretManagerServiceClient()
        resp = client.access_secret_version(request={"name": secret_name})
        return _parse_secret_payload(resp.payload.data.decode("UTF-8"))
    except (GoogleAPIError, ValueError, json.JSONDecodeError) as exc:
        _LOG.error("Failed to load MCP API key from Secret Manager (%s)", type(exc).__name__)
        raise RuntimeError(
            "MCP_API_KEY not configured — set MCP_API_KEY or configure Secret Manager"
        ) from exc


class McpApiKeyVerifier(TokenVerifier):
    """Validate Authorization: Bearer tokens against the configured MCP API key."""

    def __init__(self, expected_token: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if not expected_token:
            raise ValueError("expected_token must be non-empty")
        self._expected_token = expected_token

    async def verify_token(self, token: str) -> AccessToken | None:
        if not token:
            return None
        if secrets.compare_digest(token, self._expected_token):
            return AccessToken(
                token=token,
                client_id="justice-nexus-mcp",
                scopes=[],
            )
        return None