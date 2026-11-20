import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from schemas import (  # noqa: E402
    JudgmentRecord,
    LienRecord,
    OpenMeetingRecord,
    ProcurementRecord,
    Provenance,
    PublicRecordsRequest,
)


def test_public_records_rejects_unknown_confidence_field() -> None:
    with pytest.raises(ValidationError):
        PublicRecordsRequest.model_validate(
            {
                "id": "prr_example",
                "jurisdiction": "Example County, FL",
                "request_type": "public_records",
                "description": "Fictional request",
                "confidence": 0.9,
            }
        )


@pytest.mark.parametrize(
    "model,kwargs",
    [
        (Provenance, {"confidence": 1.0, "bogus": True}),
        (OpenMeetingRecord, {
            "id": "meet_x",
            "body_name": "Fictional Board",
            "jurisdiction": "Example County, FL",
            "meeting_type": "regular",
            "confidence": 0.5,
        }),
        (ProcurementRecord, {
            "id": "proc_x",
            "agency": "Sample Agency",
            "title": "Fictional RFP",
            "type": "IFB",
            "status": "open",
            "confidence": 0.1,
        }),
        (JudgmentRecord, {
            "id": "judg_x",
            "court": "Example Court",
            "debtor": "Fictional Debtor LLC",
            "creditor": "Fictional Creditor LLC",
            "confidence": 0.2,
        }),
        (LienRecord, {
            "id": "lien_x",
            "type": "judgment",
            "debtor": "Fictional Debtor LLC",
            "secured_party": "Fictional Secured Party LLC",
            "confidence": 0.3,
        }),
    ],
)
def test_models_forbid_extra_fields(model, kwargs: dict) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(kwargs)