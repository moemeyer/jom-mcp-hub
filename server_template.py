"""
Multi-Tenant Agency MCP Server Template

This server template is deployed separately for each agency:
- JOM Services
- NORIVO LLC
- EXLYAR LLC

Environment variables configure which agency's credentials to use.
The codebase is shared, but credentials and OAuth are isolated.

ENVIRONMENT VARIABLES:
  AGENCY_ID           - Unique agency identifier (jom, norivo, exlyar)
  SECRET_PATH         - GCP Secret Manager path (e.g., pestpro/integrations/norivo-agency)
  MCP_SERVER_BASE_URL - Public URL (e.g., https://norivo.agency-mcp.jom.services)
  AGENCY_LABEL        - Display name (e.g., "NORIVO LLC")
"""

import asyncio
import json
import logging
import os
import sys
from typing import Any

import boto3
from botocore.exceptions import ClientError
from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Mount

# Import the shared OAuth provider
try:
    from oauth.oauth_provider import OAuthProvider
except ImportError:
    # If oauth module not available, OAuth will be disabled
    OAuthProvider = None

logging.basicConfig(level=logging.INFO)
_LOG = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Agency Configuration
# ------------------------------------------------------------------

AGENCY_ID = os.environ.get("AGENCY_ID", "jom")
SECRET_PATH = os.environ.get("SECRET_PATH", f"pestpro/integrations/{AGENCY_ID}-agency")
AGENCY_LABEL = os.environ.get("AGENCY_LABEL", f"{AGENCY_ID.upper()} Agency")
SECRET_REGION = os.environ.get("SECRET_REGION", "us-east-2")

_LOG.info(f"Starting MCP server for agency: {AGENCY_LABEL} (ID: {AGENCY_ID})")
_LOG.info(f"Credentials path: {SECRET_PATH}")


# ------------------------------------------------------------------
# Credentials Loading
# ------------------------------------------------------------------

_CREDENTIALS_CACHE: dict[str, Any] = {}
_CACHE_EXPIRES: float = 0.0


async def get_agency_credentials() -> dict[str, Any]:
    """
    Load agency credentials from GCP Secret Manager.

    Expected secret structure:
    {
      "mcp_api_key": "sk_...",           # For OAuth 2.0 PKCE
      "ghl_token": "pit-...",             # GHL private integration token
      "location_ids": ["loc1", "loc2"],   # Sub-account location IDs
      "agency_name": "NORIVO LLC",
      "contact_email": "contact@norivo.ai"
    }
    """
    import time

    global _CREDENTIALS_CACHE, _CACHE_EXPIRES

    now = time.monotonic()
    if _CREDENTIALS_CACHE and now < _CACHE_EXPIRES:
        return _CREDENTIALS_CACHE

    try:
        client = boto3.client("secretsmanager", region_name=SECRET_REGION)
        resp = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: client.get_secret_value(SecretId=SECRET_PATH),
        )
        credentials = json.loads(resp["SecretString"])

        _CREDENTIALS_CACHE = credentials
        _CACHE_EXPIRES = now + 300  # 5 min cache

        _LOG.info(f"Loaded credentials for {credentials.get('agency_name', AGENCY_ID)}")
        _LOG.info(f"Location IDs: {credentials.get('location_ids', [])}")

        return credentials

    except (ClientError, json.JSONDecodeError, KeyError) as e:
        _LOG.error(f"Failed to load credentials from {SECRET_PATH}: {e}")
        raise RuntimeError(f"Cannot start server without valid credentials at {SECRET_PATH}") from e


# ------------------------------------------------------------------
# GHL API Helper
# ------------------------------------------------------------------

async def ghl_api_call(
    endpoint: str,
    method: str = "GET",
    location_id: str | None = None,
    body: dict | None = None,
    params: dict | None = None,
) -> dict:
    """
    Make authenticated GHL API call using the agency's private integration token.

    Args:
        endpoint: GHL API path (e.g., "/contacts")
        method: HTTP method
        location_id: Target location ID (uses first in list if not specified)
        body: Request body for POST/PUT/PATCH
        params: Query parameters
    """
    import httpx

    creds = await get_agency_credentials()
    token = creds["ghl_token"]

    # Default to first location if not specified
    if not location_id:
        location_id = creds["location_ids"][0]

    headers = {
        "Authorization": f"Bearer {token}",
        "Version": "2021-07-28",
        "Content-Type": "application/json",
    }

    base_url = "https://services.leadconnectorhq.com"
    url = f"{base_url}{endpoint}"

    # Add location ID to params if not in endpoint
    if params is None:
        params = {}
    if "locationId" not in params and location_id:
        params["locationId"] = location_id

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.request(
            method=method,
            url=url,
            headers=headers,
            json=body,
            params=params,
        )
        resp.raise_for_status()
        return resp.json()


# ------------------------------------------------------------------
# FastMCP Server Definition
# ------------------------------------------------------------------

mcp = FastMCP(f"{AGENCY_LABEL} Operations MCP")


@mcp.tool()
async def get_agency_info() -> dict:
    """Get information about this agency and its sub-accounts."""
    creds = await get_agency_credentials()
    return {
        "agency_id": AGENCY_ID,
        "agency_name": creds.get("agency_name", AGENCY_LABEL),
        "contact_email": creds.get("contact_email"),
        "location_ids": creds.get("location_ids", []),
        "location_count": len(creds.get("location_ids", [])),
    }


@mcp.tool()
async def search_contacts(
    query: str = "",
    location_id: str | None = None,
    limit: int = 20,
) -> dict:
    """
    Search contacts in this agency's GHL sub-accounts.

    Args:
        query: Search term (name, email, phone)
        location_id: Specific sub-account to search (searches all if not specified)
        limit: Max results per location
    """
    creds = await get_agency_credentials()

    if location_id:
        # Search single location
        return await ghl_api_call(
            "/contacts/",
            location_id=location_id,
            params={"query": query, "limit": limit},
        )

    # Search all locations for this agency
    results = []
    for loc_id in creds["location_ids"]:
        try:
            resp = await ghl_api_call(
                "/contacts/",
                location_id=loc_id,
                params={"query": query, "limit": limit},
            )
            contacts = resp.get("contacts", [])
            for contact in contacts:
                contact["_location_id"] = loc_id  # Tag which location it came from
            results.extend(contacts)
        except Exception as e:
            _LOG.warning(f"Failed to search location {loc_id}: {e}")

    return {
        "contacts": results,
        "total": len(results),
        "locations_searched": len(creds["location_ids"]),
    }


@mcp.tool()
async def get_contact(contact_id: str, location_id: str | None = None) -> dict:
    """
    Get full contact details by ID.

    Args:
        contact_id: GHL contact ID
        location_id: Location ID (required if contact_id is ambiguous)
    """
    return await ghl_api_call(f"/contacts/{contact_id}", location_id=location_id)


@mcp.tool()
async def list_calendars(location_id: str | None = None) -> dict:
    """List all calendars for this agency's locations."""
    creds = await get_agency_credentials()

    if location_id:
        return await ghl_api_call("/calendars/", location_id=location_id)

    # Get calendars from all locations
    all_calendars = []
    for loc_id in creds["location_ids"]:
        try:
            resp = await ghl_api_call("/calendars/", location_id=loc_id)
            calendars = resp.get("calendars", [])
            for cal in calendars:
                cal["_location_id"] = loc_id
            all_calendars.extend(calendars)
        except Exception as e:
            _LOG.warning(f"Failed to list calendars for {loc_id}: {e}")

    return {
        "calendars": all_calendars,
        "total": len(all_calendars),
    }


# TODO: Add remaining 150 tools from the full GHL API
# This template shows the pattern - all tools use ghl_api_call() with agency credentials


# ------------------------------------------------------------------
# OAuth 2.0 PKCE Setup
# ------------------------------------------------------------------

def build_app() -> Starlette:
    """Build the Starlette app with MCP + OAuth routes."""
    mcp_app = mcp.get_asgi_app()

    if OAuthProvider is None:
        _LOG.warning("OAuth provider not available - running MCP-only mode")
        return mcp_app

    # Each agency has its own MCP API key in the secret
    oauth = OAuthProvider(
        secret_name=SECRET_PATH,
        secret_key="mcp_api_key",
        region=SECRET_REGION,
        server_label=AGENCY_LABEL,
    )

    # Combine OAuth routes + MCP routes
    app = Starlette(
        routes=oauth.routes() + [Mount("/", app=mcp_app)]
    )

    return app


# ------------------------------------------------------------------
# Entry Point
# ------------------------------------------------------------------

if __name__ == "__main__":
    # Validate credentials on startup
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(get_agency_credentials())
    except Exception as e:
        _LOG.error(f"Startup failed: {e}")
        sys.exit(1)

    # Run as HTTP server (streamable-http transport)
    import uvicorn

    app = build_app()
    port = int(os.environ.get("PORT", 8001))

    _LOG.info(f"Starting {AGENCY_LABEL} MCP server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
