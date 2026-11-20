"""
Justice Nexus MCP Server
Extends the existing jom-mcp-hub FastMCP + Cloud Run pattern.
"""

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP

from schemas import PublicRecordsRequest, OpenMeetingRecord, JudgmentRecord, LienRecord

mcp = FastMCP(
    "Justice Nexus",
    host="0.0.0.0",
    port=int(os.environ.get("PORT", 8002)),
    stateless_http=True,
)

@mcp.tool()
async def generate_public_records_request(
    jurisdiction: str,
    description: str,
    request_type: str = "public_records",
) -> Dict[str, Any]:
    """Generate a structured public records request (Florida Sunshine / multi-state aware)."""
    citation = None
    if "florida" in jurisdiction.lower() or jurisdiction.lower() in ("fl", "fla"):
        citation = "Fla. Stat. §119.07 / §286.011"
    req = PublicRecordsRequest(
        id=f"prr_{int(datetime.utcnow().timestamp())}",
        jurisdiction=jurisdiction,
        request_type=request_type,
        description=description,
        statute_citation=citation,
    )
    return req.model_dump()

@mcp.tool()
async def search_open_meetings(
    body_name: str,
    jurisdiction: str,
    date_from: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Search open meetings (returns structured OpenMeetingRecord list)."""
    record = OpenMeetingRecord(
        id=f"meet_{int(datetime.utcnow().timestamp())}",
        body_name=body_name,
        jurisdiction=jurisdiction,
        meeting_type="regular",
        shade_meeting_claimed=False,
        confidence=0.5,
    )
    return [record.model_dump()]

@mcp.tool()
async def search_judgments_and_liens(
    debtor: str,
    jurisdiction: str,
) -> Dict[str, Any]:
    """Search judgments and liens (stub returning structured records)."""
    judgment = JudgmentRecord(
        id=f"judg_{int(datetime.utcnow().timestamp())}",
        court=jurisdiction,
        debtor=debtor,
        creditor="unknown",
        confidence=0.4,
    )
    lien = LienRecord(
        id=f"lien_{int(datetime.utcnow().timestamp())}",
        type="judgment",
        debtor=debtor,
        secured_party="unknown",
        confidence=0.4,
    )
    return {
        "judgments": [judgment.model_dump()],
        "liens": [lien.model_dump()],
        "not_legal_advice": True,
    }

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
