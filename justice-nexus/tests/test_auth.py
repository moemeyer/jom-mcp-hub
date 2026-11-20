import sys
from pathlib import Path

import httpx
import pytest
from starlette.testclient import TestClient

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from server import create_mcp  # noqa: E402


@pytest.mark.asyncio
async def test_auth_rejects_missing_token() -> None:
    mcp = create_mcp(api_key="expected-token-value")
    transport = httpx.ASGITransport(app=mcp.http_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/mcp", json={"jsonrpc": "2.0", "method": "initialize", "id": 1})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_rejects_invalid_token() -> None:
    mcp = create_mcp(api_key="expected-token-value")
    transport = httpx.ASGITransport(app=mcp.http_app())
    headers = {"Authorization": "Bearer wrong-token-value"}
    async with httpx.AsyncClient(transport=transport, base_url="http://test", headers=headers) as client:
        response = await client.post("/mcp", json={"jsonrpc": "2.0", "method": "initialize", "id": 1})
    assert response.status_code == 401


def test_auth_accepts_valid_token() -> None:
    mcp = create_mcp(api_key="expected-token-value")
    app = mcp.http_app()
    with TestClient(app, raise_server_exceptions=True) as client:
        response = client.post(
            "/mcp",
            headers={"Authorization": "Bearer expected-token-value"},
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "1.0"},
                },
                "id": 1,
            },
        )
    assert response.status_code == 200