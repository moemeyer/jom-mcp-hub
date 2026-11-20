"""
Justice Nexus MCP Server
Extends the existing jom-mcp-hub FastMCP + Cloud Run pattern.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Mount, Route

_PKG_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _PKG_DIR.parent
for _path in (_PKG_DIR, _REPO_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

try:
    from .auth import McpApiKeyVerifier, load_mcp_api_key
    from .florida import statute_citation_for_request
    from .schemas import PublicRecordsRequest
except ImportError:
    from auth import McpApiKeyVerifier, load_mcp_api_key
    from florida import statute_citation_for_request
    from schemas import PublicRecordsRequest

logging.basicConfig(level=logging.INFO)
_LOG = logging.getLogger(__name__)

_DEFAULT_PORT = 8002

_NOT_IMPLEMENTED_STUB: Dict[str, Any] = {
    "status": "not_implemented",
    "source": None,
    "not_legal_advice": True,
    "human_review_recommended": True,
}

_mcp: FastMCP | None = None


def http_port() -> int:
    """Resolve the HTTP listen port from PORT (Cloud Run contract)."""
    return int(os.environ.get("PORT", str(_DEFAULT_PORT)))


async def health(_request) -> Response:
    """Unauthenticated liveness probe (no operational data)."""
    return Response(status_code=200)


def _stub_search_result(records_key: str) -> Dict[str, Any]:
    return {records_key: [], **_NOT_IMPLEMENTED_STUB}


def _register_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    async def generate_public_records_request(
        jurisdiction: str,
        description: str,
        request_type: str = "public_records",
    ) -> Dict[str, Any]:
        """Generate a structured public records request (Florida Sunshine / multi-state aware)."""
        citation = statute_citation_for_request(request_type, jurisdiction)
        req = PublicRecordsRequest(
            id=f"prr_{uuid4()}",
            jurisdiction=jurisdiction,
            request_type=request_type,
            description=description,
            statute_citation=citation,
        )
        return req.model_dump(mode="json")

    @mcp.tool()
    async def search_open_meetings(
        body_name: str,
        jurisdiction: str,
        date_from: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search open meetings (stub until a live data source is connected)."""
        _ = body_name, jurisdiction, date_from
        return _stub_search_result("records")

    @mcp.tool()
    async def search_judgments_and_liens(
        debtor: str,
        jurisdiction: str,
    ) -> Dict[str, Any]:
        """Search judgments and liens (stub until a live data source is connected)."""
        _ = debtor, jurisdiction
        return {
            "judgments": [],
            "liens": [],
            **_NOT_IMPLEMENTED_STUB,
        }

    @mcp.tool()
    async def search_procurement(
        agency: str,
        jurisdiction: str,
        query: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search government procurement solicitations (stub until a live data source is connected)."""
        _ = agency, jurisdiction, query
        return _stub_search_result("records")


def create_mcp(*, api_key: str | None = None) -> FastMCP:
    """Build the FastMCP instance (optionally with a preloaded API key for tests)."""
    key = api_key if api_key is not None else load_mcp_api_key()
    verifier = McpApiKeyVerifier(expected_token=key)
    instance = FastMCP("Justice Nexus", auth=verifier)
    _register_tools(instance)
    return instance


def get_mcp() -> FastMCP:
    global _mcp
    if _mcp is None:
        _mcp = create_mcp()
    return _mcp


def _starlette_with_health(*, routes: list, lifespan) -> Starlette:
    return Starlette(
        routes=[Route("/health", health, methods=["GET"])] + routes,
        lifespan=lifespan,
    )


def build_app(*, api_key: str | None = None):
    """Starlette app with optional OAuth routes from the shared hub module."""
    instance = create_mcp(api_key=api_key) if api_key is not None else get_mcp()
    mcp_app = instance.http_app()
    repo_root = _PKG_DIR.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    try:
        from oauth.oauth_provider import OAuthProvider
    except ImportError:
        _LOG.warning("OAuth provider not available — MCP bearer auth only")
        return _starlette_with_health(
            routes=[Mount("/", app=mcp_app)],
            lifespan=mcp_app.lifespan,
        )

    secret_path = os.environ.get(
        "JUSTICE_NEXUS_SECRET_PATH",
        "justice-nexus-mcp-api-key",
    )
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "ghlpest-controlv2")
    oauth = OAuthProvider(
        secret_name=secret_path,
        secret_key="mcp_api_key",
        server_label="Justice Nexus",
        gcp_project=project,
    )

    return _starlette_with_health(
        routes=oauth.routes() + [Mount("/", app=mcp_app)],
        lifespan=mcp_app.lifespan,
    )


if __name__ == "__main__":
    try:
        load_mcp_api_key()
    except RuntimeError as exc:
        _LOG.error("Startup failed: %s", exc)
        sys.exit(1)

    import uvicorn

    app = build_app()
    port = http_port()
    _LOG.info("Starting Justice Nexus MCP on port %s", port)
    uvicorn.run(app, host="0.0.0.0", port=port)