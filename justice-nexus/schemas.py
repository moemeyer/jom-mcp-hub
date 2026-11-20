from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Provenance(BaseModel):
    source_url: Optional[str] = None
    retrieved_at: datetime = Field(default_factory=_utc_now)
    confidence: float = 0.0


class PublicRecordsRequest(BaseModel):
    id: str
    jurisdiction: str
    request_type: str
    description: str
    statute_citation: Optional[str] = None
    status: str = "draft"
    provenance: Provenance = Field(default_factory=Provenance)
    not_legal_advice: bool = True
    human_review_recommended: bool = True


class OpenMeetingRecord(BaseModel):
    id: str
    body_name: str
    jurisdiction: str
    meeting_type: str
    date_time: Optional[datetime] = None
    notice_period_met: Optional[bool] = None
    minutes_available: Optional[bool] = None
    recording_url: Optional[str] = None
    shade_meeting_claimed: bool = False
    shade_transcript_status: Optional[str] = None
    procurement_exemption_applied: bool = False
    provenance: Provenance = Field(default_factory=Provenance)
    not_legal_advice: bool = True


class ProcurementRecord(BaseModel):
    id: str
    solicitation_number: Optional[str] = None
    agency: str
    title: str
    type: str
    status: str
    award_amount: Optional[float] = None
    vendor: Optional[str] = None
    portal_url: Optional[str] = None
    provenance: Provenance = Field(default_factory=Provenance)


class JudgmentRecord(BaseModel):
    id: str
    case_number: Optional[str] = None
    court: str
    amount: Optional[float] = None
    debtor: str
    creditor: str
    recording_date: Optional[datetime] = None
    provenance: Provenance = Field(default_factory=Provenance)


class LienRecord(BaseModel):
    id: str
    type: str
    amount: Optional[float] = None
    debtor: str
    secured_party: str
    filing_number: Optional[str] = None
    provenance: Provenance = Field(default_factory=Provenance)