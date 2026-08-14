"""`TriagePipeline` implemented by the crewAI crew."""

from customer_support_crew.features.support_triage.adapters.crewai_pipeline.crew import (
    SupportOrchestrationCrew,
)
from customer_support_crew.features.support_triage.adapters.crewai_pipeline.result_mapper import (
    to_resolution,
)
from customer_support_crew.features.support_triage.domain.models import (
    TechnicalResolutionResult,
)
from customer_support_crew.features.support_triage.domain.policy import (
    ESCALATION_THRESHOLD,
)
from customer_support_crew.features.support_triage.ports import TicketSource


class CrewAITriagePipeline:
    def __init__(self, ticket_source: TicketSource) -> None:
        self._ticket_source = ticket_source

    def run(self, ticket_key: str) -> TechnicalResolutionResult:
        crew = SupportOrchestrationCrew(ticket_source=self._ticket_source).crew()
        crew_output = crew.kickoff(
            inputs={
                "ticket_id": ticket_key,
                # Fills the {escalation_threshold} placeholders in tasks.yaml, so the
                # prompt rule and the console gauge read the same constant.
                "escalation_threshold": ESCALATION_THRESHOLD,
            }
        )
        return to_resolution(crew_output)


def warm_up() -> None:
    """Pay the ~10s crewai/litellm import cost up front instead of inside a request.

    Importing the crew module drags in crewai, which drags in litellm, chromadb, openai
    and pyvis — about ten seconds of module loading, all of it one-time per process.
    Building the crew object itself takes well under a tenth of a second, so this
    import is the entire difference between a cold run and a warm one.

    Purely a latency optimization now. It used to also be load-bearing for correctness,
    back when the LLMs were class-body attributes reading `os.getenv` at import time.
    """
    from customer_support_crew.features.support_triage.adapters.crewai_pipeline import (  # noqa: F401
        crew as _crew,
    )
