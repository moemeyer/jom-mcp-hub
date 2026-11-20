"""Florida jurisdiction detection and statute citations."""

from __future__ import annotations

import re

_FLORIDA_RE = re.compile(
    r"""
    (?:
        \bflorida\b
        | \bfla\.?\b
        | \bfl\b
        | ,\s*FL\b
        | ,\s*Florida\b
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

CITATION_PUBLIC_RECORDS = "Fla. Stat. ch. 119 (§119.07)"
CITATION_OPEN_MEETINGS = "Fla. Stat. §286.011"


def is_florida_jurisdiction(jurisdiction: str) -> bool:
    """Return True when the jurisdiction string refers to Florida."""
    if not jurisdiction or not jurisdiction.strip():
        return False
    return _FLORIDA_RE.search(jurisdiction.strip()) is not None


def statute_citation_for_request(request_type: str, jurisdiction: str) -> str | None:
    """Map request type to Florida citations when jurisdiction is Florida."""
    if not is_florida_jurisdiction(jurisdiction):
        return None
    normalized = (request_type or "public_records").strip().lower()
    if normalized in ("open_meetings", "open_meeting", "sunshine"):
        return CITATION_OPEN_MEETINGS
    return CITATION_PUBLIC_RECORDS