import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_WORKSPACE = Path(__file__).resolve().parents[2]
if str(_WORKSPACE) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE))
_PKG = Path(__file__).resolve().parents[1]
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))

from auth import _DEFAULT_SECRET_PATH, load_mcp_api_key  # noqa: E402
from oauth.gcp_secret_resource import (  # noqa: E402
    is_full_secret_version_resource_name,
    resolve_secret_version_resource_name,
)
from oauth.oauth_provider import OAuthProvider  # noqa: E402

_FULL = (
    "projects/example-project/secrets/justice-nexus-mcp-api-key/versions/latest"
)


def test_default_secret_path_is_bare_id() -> None:
    assert _DEFAULT_SECRET_PATH == "justice-nexus-mcp-api-key"
    assert "/" not in _DEFAULT_SECRET_PATH


@pytest.mark.parametrize(
    "secret_path,project,expected",
    [
        (
            "justice-nexus-mcp-api-key",
            "ghlpest-controlv2",
            "projects/ghlpest-controlv2/secrets/justice-nexus-mcp-api-key/versions/latest",
        ),
        (
            "pestpro/integrations/justice-nexus",
            "ghlpest-controlv2",
            "projects/ghlpest-controlv2/secrets/pestpro/integrations/justice-nexus/versions/latest",
        ),
        (_FULL, "ignored-project", _FULL),
    ],
)
def test_resolve_secret_version_resource_name(secret_path: str, project: str, expected: str) -> None:
    assert resolve_secret_version_resource_name(secret_path, project=project) == expected
    if secret_path == _FULL:
        assert is_full_secret_version_resource_name(secret_path)


@patch("auth.secretmanager.SecretManagerServiceClient")
def test_auth_load_uses_resolved_bare_secret_name(mock_client_ctor: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MCP_API_KEY", raising=False)
    monkeypatch.delenv("JUSTICE_NEXUS_MCP_API_KEY", raising=False)
    monkeypatch.setenv("JUSTICE_NEXUS_SECRET_PATH", "justice-nexus-mcp-api-key")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "sample-project-123")

    mock_client = MagicMock()
    mock_client.access_secret_version.return_value = MagicMock(
        payload=MagicMock(data=json.dumps({"mcp_api_key": "resolved-key"}).encode())
    )
    mock_client_ctor.return_value = mock_client

    assert load_mcp_api_key() == "resolved-key"
    mock_client.access_secret_version.assert_called_once()
    called_name = mock_client.access_secret_version.call_args.kwargs["request"]["name"]
    assert called_name == (
        "projects/sample-project-123/secrets/justice-nexus-mcp-api-key/versions/latest"
    )


@patch("auth.secretmanager.SecretManagerServiceClient")
def test_auth_load_passes_full_resource_name_unchanged(
    mock_client_ctor: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MCP_API_KEY", raising=False)
    monkeypatch.delenv("JUSTICE_NEXUS_MCP_API_KEY", raising=False)
    monkeypatch.setenv("JUSTICE_NEXUS_SECRET_PATH", _FULL)
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "other-project")

    mock_client = MagicMock()
    mock_client.access_secret_version.return_value = MagicMock(
        payload=MagicMock(data=json.dumps({"mcp_api_key": "full-path-key"}).encode())
    )
    mock_client_ctor.return_value = mock_client

    assert load_mcp_api_key() == "full-path-key"
    called_name = mock_client.access_secret_version.call_args.kwargs["request"]["name"]
    assert called_name == _FULL


@pytest.mark.asyncio
@patch("oauth.oauth_provider.secretmanager.SecretManagerServiceClient")
async def test_oauth_provider_resolves_bare_secret_name(mock_client_ctor: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.access_secret_version.return_value = MagicMock(
        payload=MagicMock(data=json.dumps({"mcp_api_key": "oauth-key"}).encode())
    )
    mock_client_ctor.return_value = mock_client

    provider = OAuthProvider(
        secret_name="justice-nexus-mcp-api-key",
        secret_key="mcp_api_key",
        server_label="Justice Nexus",
        gcp_project="sample-project-123",
    )
    key = await provider._get_api_key()
    assert key == "oauth-key"
    called_name = mock_client.access_secret_version.call_args.kwargs["request"]["name"]
    assert called_name == (
        "projects/sample-project-123/secrets/justice-nexus-mcp-api-key/versions/latest"
    )


@pytest.mark.asyncio
@patch("oauth.oauth_provider.secretmanager.SecretManagerServiceClient")
async def test_oauth_provider_passes_full_resource_name_unchanged(mock_client_ctor: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.access_secret_version.return_value = MagicMock(
        payload=MagicMock(data=json.dumps({"mcp_api_key": "oauth-full"}).encode())
    )
    mock_client_ctor.return_value = mock_client

    provider = OAuthProvider(
        secret_name=_FULL,
        secret_key="mcp_api_key",
        gcp_project="other-project",
    )
    key = await provider._get_api_key()
    assert key == "oauth-full"
    called_name = mock_client.access_secret_version.call_args.kwargs["request"]["name"]
    assert called_name == _FULL