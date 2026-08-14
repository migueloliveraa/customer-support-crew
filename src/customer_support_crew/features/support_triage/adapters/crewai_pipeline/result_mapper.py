"""Turn a `CrewOutput` into a validated `TechnicalResolutionResult`.

crewAI does not consistently populate its parsed fields, so there are three tiers to
try. Tiers 2 and 3 hand back raw dicts that never met the schema, so the score bounds
and the status enum would not have been applied to them — they are forced through the
model here. `frustration_score` decides whether a human ever sees the ticket, so a
degraded result is worth failing on rather than rendering.
"""

import json

from pydantic import ValidationError

from customer_support_crew.core.errors import PipelineError
from customer_support_crew.features.support_triage.domain.models import (
    TechnicalResolutionResult,
)


def to_resolution(crew_output) -> TechnicalResolutionResult:
    pydantic_result = getattr(crew_output, "pydantic", None)
    if isinstance(pydantic_result, TechnicalResolutionResult):
        return pydantic_result
    if pydantic_result is not None:
        return _validate(pydantic_result.model_dump(mode="json"))

    json_dict = getattr(crew_output, "json_dict", None)
    if json_dict is not None:
        return _validate(json_dict)

    try:
        payload = json.loads(crew_output.raw)
    except (AttributeError, TypeError, ValueError) as exc:
        raise PipelineError(
            f"The crew returned output we could not parse: {exc}"
        ) from exc
    return _validate(payload)


def _validate(payload) -> TechnicalResolutionResult:
    """Force a fallback-tier payload through the schema, or fail loudly."""
    try:
        return TechnicalResolutionResult.model_validate(payload)
    except ValidationError as exc:
        raise PipelineError(
            f"The crew returned output that failed validation: {exc}"
        ) from exc
