"""Single callable entry point for the support crew, shared by the CLI and the web app."""

import json
import os
import re

from dotenv import load_dotenv
from pydantic import ValidationError

# crew.py builds its LLM objects in the class body, so os.getenv runs at import
# time. Load .env here, before anything imports that module.
load_dotenv()

# Re-exported so the CLI and the web app have one import site for the outcome
# vocabulary. Safe at module scope: schemas.py imports only pydantic, so it
# cannot reintroduce the getenv race that keeps the crew import lazy below.
from customer_support_crew.config.schemas import (  # noqa: E402
    ResolutionStatus,
    TechnicalResolutionResult,
)

TICKET_KEY_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9]*-\d+$")

# Display only. The rule that actually drives escalation is prose in
# config/tasks.yaml (resolution_task); keep this in sync with it by hand.
ESCALATION_THRESHOLD = 7


class PipelineError(RuntimeError):
    """The crew ran but did not return a resolution we could parse."""


class InvalidTicketKey(ValueError):
    """The supplied string is not shaped like a Jira issue key."""


def normalize_ticket_id(raw: str) -> str:
    """Uppercase and validate a Jira key so we fail before spending an LLM call."""
    ticket_id = (raw or "").strip().upper()
    if not TICKET_KEY_PATTERN.match(ticket_id):
        raise InvalidTicketKey(
            f"'{raw}' is not a Jira issue key. Use a key like CREWAISUP-10."
        )
    return ticket_id


def run_pipeline(ticket_id: str) -> dict:
    """Run triage + resolution for one ticket and return the resolution as a dict.

    Raises InvalidTicketKey, PipelineError, or whatever the crew itself raises.
    """
    ticket_id = normalize_ticket_id(ticket_id)
    os.makedirs("output", exist_ok=True)

    # Imported lazily so load_dotenv() above always wins the race described there.
    from customer_support_crew.crew import SupportOrchestrationCrew

    crew_output = SupportOrchestrationCrew().crew().kickoff(inputs={"ticket_id": ticket_id})
    return extract_result(crew_output)


def extract_result(crew_output) -> dict:
    """crewAI populates one of three fields depending on how the model replied."""
    pydantic_result = getattr(crew_output, "pydantic", None)
    if pydantic_result is not None:
        # mode="json" so ResolutionStatus lands as a plain string, not an enum member.
        return pydantic_result.model_dump(mode="json")

    # Tiers 2 and 3 hand back raw dicts that never met the schema, so the score
    # bounds and the status enum would not apply to them. Validate here instead:
    # frustration_score decides whether a human ever sees the ticket, and a
    # degraded result is worth failing on rather than rendering.
    json_dict = getattr(crew_output, "json_dict", None)
    if json_dict is not None:
        return _validate(json_dict)

    try:
        return _validate(json.loads(crew_output.raw))
    except (AttributeError, TypeError, ValueError) as exc:
        raise PipelineError(f"The crew returned output we could not parse: {exc}") from exc


def _validate(payload) -> dict:
    """Force a fallback-tier payload through the schema, or fail loudly."""
    try:
        return TechnicalResolutionResult.model_validate(payload).model_dump(mode="json")
    except ValidationError as exc:
        raise PipelineError(f"The crew returned output that failed validation: {exc}") from exc
