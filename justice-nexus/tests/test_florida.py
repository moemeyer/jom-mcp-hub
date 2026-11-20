import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from florida import (  # noqa: E402
    CITATION_OPEN_MEETINGS,
    CITATION_PUBLIC_RECORDS,
    is_florida_jurisdiction,
    statute_citation_for_request,
)


@pytest.mark.parametrize(
    "jurisdiction,expected",
    [
        ("Florida", True),
        ("fl", True),
        ("Fla.", True),
        ("Fictional County, FL", True),
        ("Example City, Florida", True),
        ("Georgia", False),
        ("New York, NY", False),
        ("", False),
    ],
)
def test_is_florida_jurisdiction(jurisdiction: str, expected: bool) -> None:
    assert is_florida_jurisdiction(jurisdiction) is expected


def test_public_records_citation_only_ch119() -> None:
    assert (
        statute_citation_for_request("public_records", "Example Metro County, FL")
        == CITATION_PUBLIC_RECORDS
    )
    assert CITATION_OPEN_MEETINGS not in (CITATION_PUBLIC_RECORDS)


def test_open_meetings_citation_286011() -> None:
    assert (
        statute_citation_for_request("open_meetings", "Florida")
        == CITATION_OPEN_MEETINGS
    )


def test_non_florida_has_no_citation() -> None:
    assert statute_citation_for_request("public_records", "Texas") is None