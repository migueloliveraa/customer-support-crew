import pytest

from customer_support_crew.core.errors import InvalidTicketKey
from customer_support_crew.features.support_triage.domain.ticket_key import (
    normalize_ticket_id,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("CREWAISUP-10", "CREWAISUP-10"),
        ("crewaisup-10", "CREWAISUP-10"),
        ("  sup-1  ", "SUP-1"),
        ("AB2C-99", "AB2C-99"),
    ],
)
def test_accepts_and_normalizes(raw, expected):
    assert normalize_ticket_id(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", "   ", None, "nope", "SUP", "-10", "1SUP-10", "SUP-", "SUP-1x", "SUP 10"],
)
def test_rejects_non_keys(raw):
    with pytest.raises(InvalidTicketKey):
        normalize_ticket_id(raw)
