import sys
from pathlib import Path

import pytest
from starlette.testclient import TestClient

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from server import build_app, http_port  # noqa: E402


def test_health_unauthenticated_returns_200_empty_body() -> None:
    app = build_app(api_key="health-check-token")
    with TestClient(app, raise_server_exceptions=True) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.content in (b"", b"null")
    assert response.text.strip() == ""


def test_http_port_reads_port_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORT", "9123")
    assert http_port() == 9123