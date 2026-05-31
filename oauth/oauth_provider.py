"""
OAuth 2.0 PKCE Authorization Server for JOM MCP servers (FastMCP / Starlette)

PURPOSE
-------
Claude.ai web custom connectors require OAuth 2.0 PKCE — they have no field for
a raw Bearer token. This module adds the four OAuth endpoints required by the
MCP spec so Claude.ai can connect to any of the three JOM MCP servers.

The access_token returned from /token IS the MCP API key fetched from Secrets
Manager, so existing bearer auth middleware needs zero changes.

ENDPOINTS ADDED
---------------
  GET  /.well-known/oauth-authorization-server  — RFC 8414 metadata (auto-discovered)
  GET  /authorize                                — HTML key-entry form shown to user
  POST /authorize                                — validate key → redirect with auth code
  POST /token                                    — PKCE verify → return access_token

INTEGRATION
-----------
Copy this file (and oauth/__init__.py) into your server repo alongside server.py.
Then in server.py, after you build the Starlette app, add the OAuth routes:

    # server.py (existing pattern)
    from fastmcp import FastMCP
    from starlette.applications import Starlette
    from starlette.routing import Mount
    from oauth.oauth_provider import OAuthProvider

    mcp = FastMCP("briostack-mcp")
    # ... tool definitions ...

    mcp_app = mcp.streamable_http_app()           # or however you build it

    oauth = OAuthProvider(
        secret_name="pestpro/integrations/mcp-api-key",
        secret_key="api_key",
        region="us-east-2",
    )
    app = Starlette(routes=oauth.routes() + [Mount("/", app=mcp_app)])

    if __name__ == "__main__":
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8001)

ENVIRONMENT VARIABLE (optional)
--------------------------------
  MCP_SERVER_BASE_URL=https://your-apprunner-url.awsapprunner.com
  If set, used for the issuer/endpoint URLs in the discovery metadata.
  If not set, derived from the incoming request (works in most cases).

DEPENDENCIES
------------
  boto3, starlette  (already in requirements.txt for all three servers)
"""

import asyncio
import base64
import hashlib
import json
import os
import secrets
import time
import urllib.parse
from typing import Optional

import boto3
from botocore.exceptions import ClientError
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Route


# ---------------------------------------------------------------------------
# HTML authorize form — served to the user by Claude.ai's OAuth redirect
# ---------------------------------------------------------------------------
_FORM_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>JOM MCP Hub — Authorize Access</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
         background:#f9fafb;color:#111827;display:flex;min-height:100vh;
         align-items:center;justify-content:center;padding:24px}}
    .card{{background:#fff;border:1px solid #d1d5db;border-radius:12px;
           padding:40px 36px;max-width:440px;width:100%;
           box-shadow:0 4px 6px rgba(0,0,0,.07),0 1px 3px rgba(0,0,0,.06)}}
    .logo{{color:#1a7a1a;font-weight:800;font-size:1.05rem;margin-bottom:4px}}
    .logo span{{color:#6b7280;font-weight:400}}
    .server-name{{font-size:.78rem;color:#6b7280;margin-bottom:20px;
                  padding:4px 10px;background:#f0fdf4;border:1px solid #bbf7d0;
                  border-radius:20px;display:inline-block}}
    h1{{font-size:1.1rem;font-weight:700;margin-bottom:8px}}
    .desc{{font-size:.83rem;color:#6b7280;line-height:1.6;margin-bottom:22px}}
    label{{display:block;font-size:.8rem;font-weight:600;color:#374151;margin-bottom:6px}}
    input[type=password]{{width:100%;padding:10px 12px;border:1px solid #d1d5db;
                          border-radius:8px;font-size:.9rem;outline:none;
                          font-family:monospace;letter-spacing:.05em}}
    input[type=password]:focus{{border-color:#1a7a1a;
                                box-shadow:0 0 0 3px rgba(26,122,26,.12)}}
    .err{{background:#fef2f2;border:1px solid #fecaca;border-radius:8px;
          padding:10px 12px;font-size:.82rem;color:#dc2626;margin-bottom:16px}}
    button{{width:100%;padding:11px;background:#1a7a1a;color:#fff;border:none;
            border-radius:8px;font-size:.88rem;font-weight:700;cursor:pointer;
            margin-top:14px;transition:background .15s}}
    button:hover{{background:#145214}}
    .hint{{font-size:.75rem;color:#9ca3af;margin-top:12px;line-height:1.5}}
    .hint a{{color:#1a7a1a;text-decoration:none}}
    .hint a:hover{{text-decoration:underline}}
  </style>
</head>
<body>
<div class="card">
  <div class="logo">🐛 JOM <span>/ mcp.jom.services</span></div>
  <div class="server-name">{server_label}</div>
  <h1>Authorize MCP Access</h1>
  <p class="desc">
    <strong>{client_id}</strong> is requesting access to this MCP server.
    Enter your MCP API key — it was included in your access approval email.
  </p>
  {error_html}
  <form method="post" action="/authorize">
    <input type="hidden" name="response_type"         value="{response_type}"/>
    <input type="hidden" name="client_id"             value="{client_id}"/>
    <input type="hidden" name="redirect_uri"          value="{redirect_uri}"/>
    <input type="hidden" name="code_challenge"        value="{code_challenge}"/>
    <input type="hidden" name="code_challenge_method" value="{code_challenge_method}"/>
    <input type="hidden" name="state"                 value="{state}"/>
    <label for="api_key">MCP API Key</label>
    <input type="password" id="api_key" name="api_key"
           placeholder="Paste your API key here" autocomplete="off" autofocus/>
    <button type="submit">Authorize Access →</button>
  </form>
  <p class="hint">
    Don't have a key?
    <a href="https://mcp.jom.services/request-access.html">Request access here</a>.
  </p>
</div>
</body>
</html>"""


class OAuthProvider:
    """
    OAuth 2.0 PKCE authorization server.

    Validates the entered API key against AWS Secrets Manager.
    The access_token returned from /token equals the actual MCP API key,
    so the existing Bearer token middleware requires no changes.
    """

    def __init__(
        self,
        secret_name: str = "pestpro/integrations/mcp-api-key",
        secret_key: str = "api_key",
        region: str = "us-east-2",
        server_label: str = "JOM MCP Server",
        code_ttl: int = 300,
    ):
        """
        secret_name  — AWS Secrets Manager secret containing the API key.
        secret_key   — JSON key within the secret (default: "api_key").
        region       — AWS region for Secrets Manager.
        server_label — Displayed in the HTML authorize form (e.g. "BrioStack Operations").
        code_ttl     — Auth code lifetime in seconds (default: 5 min).
        """
        self.secret_name = secret_name
        self.secret_key = secret_key
        self.region = region
        self.server_label = server_label
        self.code_ttl = code_ttl

        self._codes: dict[str, dict] = {}
        self._lock = asyncio.Lock()
        self._cached_key: Optional[str] = None
        self._cache_expires: float = 0.0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _base_url(self, request: Request) -> str:
        override = os.environ.get("MCP_SERVER_BASE_URL", "").rstrip("/")
        if override:
            return override
        return f"{request.url.scheme}://{request.url.netloc}"

    async def _get_api_key(self) -> str:
        now = time.monotonic()
        if self._cached_key and now < self._cache_expires:
            return self._cached_key
        client = boto3.client("secretsmanager", region_name=self.region)
        resp = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client.get_secret_value(SecretId=self.secret_name),
        )
        payload = json.loads(resp["SecretString"])
        self._cached_key = payload[self.secret_key]
        self._cache_expires = now + 300
        return self._cached_key

    @staticmethod
    def _verify_pkce(verifier: str, challenge: str, method: str) -> bool:
        if method != "S256":
            return False
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        computed = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        return secrets.compare_digest(computed, challenge)

    def _purge_expired(self) -> None:
        now = time.time()
        self._codes = {k: v for k, v in self._codes.items() if v["expires"] > now}

    def _render_form(self, *, params: dict, error: str = "") -> HTMLResponse:
        error_html = f'<div class="err">⚠ {error}</div>' if error else ""
        html = _FORM_HTML.format(
            server_label=self.server_label,
            error_html=error_html,
            response_type=params.get("response_type", "code"),
            client_id=params.get("client_id", "claude.ai"),
            redirect_uri=params.get("redirect_uri", ""),
            code_challenge=params.get("code_challenge", ""),
            code_challenge_method=params.get("code_challenge_method", "S256"),
            state=params.get("state", ""),
        )
        return HTMLResponse(html)

    # ------------------------------------------------------------------
    # Endpoint handlers
    # ------------------------------------------------------------------

    async def handle_metadata(self, request: Request) -> JSONResponse:
        base = self._base_url(request)
        return JSONResponse(
            {
                "issuer": base,
                "authorization_endpoint": f"{base}/authorize",
                "token_endpoint": f"{base}/token",
                "response_types_supported": ["code"],
                "grant_types_supported": ["authorization_code"],
                "code_challenge_methods_supported": ["S256"],
                "token_endpoint_auth_methods_supported": ["none"],
            },
            headers={"Cache-Control": "no-store"},
        )

    async def handle_authorize(self, request: Request) -> Response:
        if request.method == "GET":
            p = dict(request.query_params)
            return self._render_form(params=p)

        # POST — process the submitted form
        form = await request.form()
        p = {k: form.get(k, "") for k in (
            "response_type", "client_id", "redirect_uri",
            "code_challenge", "code_challenge_method", "state",
        )}
        api_key = (form.get("api_key") or "").strip()

        if not api_key:
            return self._render_form(params=p, error="Please enter your API key.")

        if not p["redirect_uri"]:
            return JSONResponse(
                {"error": "invalid_request", "error_description": "redirect_uri is required"},
                status_code=400,
            )

        if p["code_challenge_method"] not in ("S256",):
            return JSONResponse(
                {"error": "invalid_request", "error_description": "Only S256 code_challenge_method is supported"},
                status_code=400,
            )

        try:
            valid_key = await self._get_api_key()
        except (ClientError, KeyError, json.JSONDecodeError, Exception):
            return self._render_form(
                params=p,
                error="Server configuration error. Contact the hub administrator.",
            )

        if not secrets.compare_digest(api_key, valid_key):
            return self._render_form(params=p, error="Invalid API key. Check your approval email and try again.")

        code = secrets.token_urlsafe(32)
        async with self._lock:
            self._purge_expired()
            self._codes[code] = {
                "code_challenge": p["code_challenge"],
                "code_challenge_method": p["code_challenge_method"],
                "redirect_uri": p["redirect_uri"],
                "api_key": valid_key,
                "expires": time.time() + self.code_ttl,
            }

        qs_params = {"code": code}
        if p["state"]:
            qs_params["state"] = p["state"]
        sep = "&" if "?" in p["redirect_uri"] else "?"
        location = p["redirect_uri"] + sep + urllib.parse.urlencode(qs_params)
        return RedirectResponse(location, status_code=302)

    async def handle_token(self, request: Request) -> JSONResponse:
        content_type = request.headers.get("content-type", "")
        if "application/x-www-form-urlencoded" in content_type:
            form = await request.form()
            grant_type    = form.get("grant_type", "")
            code          = form.get("code", "")
            code_verifier = form.get("code_verifier", "")
            redirect_uri  = form.get("redirect_uri", "")
        else:
            try:
                body = await request.json()
            except Exception:
                return JSONResponse({"error": "invalid_request"}, status_code=400)
            grant_type    = body.get("grant_type", "")
            code          = body.get("code", "")
            code_verifier = body.get("code_verifier", "")
            redirect_uri  = body.get("redirect_uri", "")

        if grant_type != "authorization_code":
            return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)

        if not code or not code_verifier:
            return JSONResponse(
                {"error": "invalid_request", "error_description": "code and code_verifier are required"},
                status_code=400,
            )

        async with self._lock:
            self._purge_expired()
            record = self._codes.pop(code, None)

        if not record:
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "Authorization code not found or expired"},
                status_code=400,
            )

        if not self._verify_pkce(code_verifier, record["code_challenge"], record["code_challenge_method"]):
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "PKCE verification failed"},
                status_code=400,
            )

        return JSONResponse(
            {
                "access_token": record["api_key"],
                "token_type": "Bearer",
                "expires_in": 3600,
            },
            headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
        )

    # ------------------------------------------------------------------
    # Route list — include in your Starlette app
    # ------------------------------------------------------------------

    def routes(self) -> list[Route]:
        return [
            Route(
                "/.well-known/oauth-authorization-server",
                self.handle_metadata,
                methods=["GET"],
            ),
            Route(
                "/authorize",
                self.handle_authorize,
                methods=["GET", "POST"],
            ),
            Route(
                "/token",
                self.handle_token,
                methods=["POST"],
            ),
        ]
