import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from auth import load_mcp_api_key  # noqa: E402
from server import create_mcp  # noqa: E402


def _clear_api_key_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MCP_API_KEY", raising=False)
    monkeypatch.delenv("JUSTICE_NEXUS_MCP_API_KEY", raising=False)


def _mock_secret_manager_failure(mock_client_ctor: MagicMock) -> None:
    from google.api_core.exceptions import GoogleAPIError

    mock_client = MagicMock()
    mock_client.access_secret_version.side_effect = GoogleAPIError("Secret Manager unreachable")
    mock_client_ctor.return_value = mock_client


@patch("auth.secretmanager.SecretManagerServiceClient")
def test_load_mcp_api_key_fails_without_env_or_secret_manager(
    mock_client_ctor: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_api_key_env(monkeypatch)
    _mock_secret_manager_failure(mock_client_ctor)

    with pytest.raises(RuntimeError, match="MCP_API_KEY not configured"):
        load_mcp_api_key()


@patch("auth.secretmanager.SecretManagerServiceClient")
def test_create_mcp_refuses_without_configured_key(
    mock_client_ctor: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_api_key_env(monkeypatch)
    _mock_secret_manager_failure(mock_client_ctor)

    with pytest.raises(RuntimeError, match="MCP_API_KEY not configured"):
        create_mcp()