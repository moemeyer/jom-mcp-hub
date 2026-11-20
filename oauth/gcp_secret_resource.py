"""GCP Secret Manager version resource name resolution (shared by hub MCP servers)."""

from __future__ import annotations

import re

# projects/{project}/secrets/{secret_id}/versions/{version}
_FULL_SECRET_VERSION_RE = re.compile(
    r"^projects/[^/]+/secrets/[^/]+/versions/[^/]+$"
)


def is_full_secret_version_resource_name(secret_path: str) -> bool:
    """Return True when secret_path is a complete Secret Manager version resource name."""
    return bool(_FULL_SECRET_VERSION_RE.match(secret_path.strip()))


def resolve_secret_version_resource_name(secret_path: str, *, project: str) -> str:
    """
    Resolve a configured secret path to a Secret Manager version resource name.

    - Bare secret ids (e.g. ``justice-nexus-mcp-api-key``) become
      ``projects/<project>/secrets/<id>/versions/latest``.
    - Legacy paths containing ``/`` but not a full resource name are treated as
      bare ids (same construction), not passed through raw.
    - Full resource names matching ``projects/.../secrets/.../versions/...`` are
      returned unchanged.
    """
    trimmed = secret_path.strip()
    if not trimmed:
        raise ValueError("secret_path must be non-empty")
    if is_full_secret_version_resource_name(trimmed):
        return trimmed
    return f"projects/{project}/secrets/{trimmed}/versions/latest"