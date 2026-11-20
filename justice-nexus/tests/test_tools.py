import json
import sys
from pathlib import Path

import pytest
from fastmcp import Client
from pydantic import ValidationError

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from schemas import (  # noqa: E402
    JudgmentRecord,
    LienRecord,
    OpenMeetingRecord,
    ProcurementRecord,
    PublicRecordsRequest,
)
from server import create_mcp  # noqa: E402


@pytest.fixture
def mcp_server():
    return create_mcp(api_key="pytest-justice-nexus-token")


def _tool_payload(result) -> dict:
    block = result.content[0]
    if hasattr(block, "text"):
        return json.loads(block.text)
    return block.structured_content


@pytest.mark.asyncio
async def test_generate_public_records_request_schema_valid(mcp_server) -> None:
    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "generate_public_records_request",
            {
                "jurisdiction": "Example County, FL",
                "description": "Agenda packets for a sample board (fictional).",
            },
        )
    data = _tool_payload(result)
    parsed = PublicRecordsRequest.model_validate(data)
    assert parsed.not_legal_advice is True
    assert parsed.human_review_recommended is True
    assert parsed.id.startswith("prr_")
    assert parsed.statute_citation == "Fla. Stat. ch. 119 (§119.07)"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name,args",
    [
        (
            "search_open_meetings",
            {
                "body_name": "Sample Advisory Board",
                "jurisdiction": "Example County, FL",
            },
        ),
        (
            "search_procurement",
            {"agency": "Sample Agency", "jurisdiction": "Florida"},
        ),
        (
            "search_judgments_and_liens",
            {"debtor": "Fictional Debtor LLC", "jurisdiction": "Example County, FL"},
        ),
    ],
)
async def test_stub_tools_not_implemented(mcp_server, tool_name: str, args: dict) -> None:
    async with Client(mcp_server) as client:
        result = await client.call_tool(tool_name, args)
    data = _tool_payload(result)
    assert data["status"] == "not_implemented"
    assert data["source"] is None
    assert data["not_legal_advice"] is True

    if tool_name == "search_judgments_and_liens":
        assert data["judgments"] == []
        assert data["liens"] == []
        assert isinstance(data["judgments"], list)
        assert isinstance(data["liens"], list)
    else:
        assert data["records"] == []
        if tool_name == "search_open_meetings":
            for row in data["records"]:
                OpenMeetingRecord.model_validate(row)
        else:
            for row in data["records"]:
                ProcurementRecord.model_validate(row)

    serialized = json.dumps(data).lower()
    assert "unknown" not in serialized
    assert '"confidence":' not in serialized


@pytest.mark.asyncio
async def test_unique_request_ids(mcp_server) -> None:
    async with Client(mcp_server) as client:
        first = await client.call_tool(
            "generate_public_records_request",
            {"jurisdiction": "Florida", "description": "Sample A"},
        )
        second = await client.call_tool(
            "generate_public_records_request",
            {"jurisdiction": "Florida", "description": "Sample B"},
        )
    a = _tool_payload(first)
    b = _tool_payload(second)
    assert a["id"] != b["id"]


def test_public_records_model_rejects_invalid() -> None:
    with pytest.raises(ValidationError):
        PublicRecordsRequest.model_validate(
            {
                "id": 12345,
                "jurisdiction": "FL",
                "request_type": "public_records",
                "description": "x",
            }
        )