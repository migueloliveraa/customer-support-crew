"""The three-tier fallback, and what happens when a fallback tier is garbage."""

import json
from types import SimpleNamespace

import pytest

from customer_support_crew.core.errors import PipelineError
from customer_support_crew.features.support_triage.adapters.crewai_pipeline.result_mapper import (
    to_resolution,
)
from customer_support_crew.features.support_triage.domain.models import ResolutionStatus

from tests.conftest import make_result

VALID_PAYLOAD = {
    "ticket_id": "CREWAISUP-6",
    "frustration_score": 9,
    "score_rationale": "Threatened to churn.",
    "resolution_status": "escalated_to_human",
    "email_response_template": None,
    "internal_escalation_notes": "Handover.",
}


def _output(**fields):
    """A stand-in CrewOutput: every tier absent unless the test supplies it."""
    return SimpleNamespace(**{"pydantic": None, "json_dict": None, "raw": None, **fields})


def test_tier1_pydantic_is_used_as_is():
    expected = make_result()
    out = _output()
    out.pydantic = expected
    assert to_resolution(out) is expected


def test_tier2_json_dict_is_validated():
    result = to_resolution(_output(json_dict=VALID_PAYLOAD))
    assert result.resolution_status is ResolutionStatus.ESCALATED_TO_HUMAN
    assert result.escalated is True


def test_tier3_raw_string_is_parsed_and_validated():
    result = to_resolution(_output(raw=json.dumps(VALID_PAYLOAD)))
    assert result.ticket_id == "CREWAISUP-6"


def test_unparseable_raw_raises_pipeline_error():
    with pytest.raises(PipelineError, match="could not parse"):
        to_resolution(_output(raw="I could not complete the task."))


@pytest.mark.parametrize(
    "field, bad_value",
    [
        ("frustration_score", 85),
        ("frustration_score", 0),
        ("resolution_status", "escalated"),
        ("resolution_status", "drafted"),
    ],
)
def test_out_of_contract_values_fail_validation(field, bad_value):
    payload = {**VALID_PAYLOAD, field: bad_value}
    with pytest.raises(PipelineError, match="failed validation"):
        to_resolution(_output(json_dict=payload))
