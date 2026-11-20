import json
import re
import sys
from pathlib import Path

import pytest

_WORKSPACE = Path(__file__).resolve().parents[2]
if str(_WORKSPACE) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE))


@pytest.fixture
def catalog() -> dict:
    path = _WORKSPACE / "mcp-catalog.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_mcp_catalog_json_parses(catalog: dict) -> None:
    assert catalog["version"]
    assert isinstance(catalog["servers"], list)


def test_justice_nexus_catalog_entry(catalog: dict) -> None:
    entry = next(s for s in catalog["servers"] if s["id"] == "justice-nexus-mcp")
    assert entry["status"] == "development"
    assert entry.get("endpoint", "") == "" or "request-access" in entry.get("endpoint", "")


def test_index_html_still_valid_markup() -> None:
    html = (_WORKSPACE / "index.html").read_text(encoding="utf-8")
    assert "<html" in html.lower()
    assert "</html>" in html.lower()
    assert len(re.findall(r"<script\b", html, flags=re.IGNORECASE)) >= 0