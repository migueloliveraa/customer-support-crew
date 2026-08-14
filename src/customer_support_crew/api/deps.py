"""Composition root.

The only module that knows `JiraTicketSource` and `CrewAITriagePipeline` are the
concrete implementations. Routes, the web console and the CLI ask for a
`ResolveTicketUseCase` and get one; tests override `get_resolve_ticket_use_case` with a
fake and never touch Jira or an LLM.

The crewAI import is deliberately kept inside the builder rather than at module scope:
importing it drags in litellm, chromadb and friends, about ten seconds. Doing that at
import time would delay the server binding its port and would make `warm_up()`
pointless. Correctness no longer depends on the laziness — only startup latency does.
"""

from functools import lru_cache

from customer_support_crew.core.settings import get_settings
from customer_support_crew.features.support_triage.adapters.file_resolution_store import (
    FileResolutionStore,
)
from customer_support_crew.features.support_triage.adapters.jira_ticket_source import (
    JiraTicketSource,
)
from customer_support_crew.features.support_triage.application.resolve_ticket import (
    ResolveTicketUseCase,
)


@lru_cache(maxsize=1)
def get_resolve_ticket_use_case() -> ResolveTicketUseCase:
    """Build (once) the use case wired to the real adapters."""
    from customer_support_crew.features.support_triage.adapters.crewai_pipeline.pipeline import (
        CrewAITriagePipeline,
    )

    settings = get_settings()
    ticket_source = JiraTicketSource(settings)
    return ResolveTicketUseCase(
        pipeline=CrewAITriagePipeline(ticket_source),
        store=FileResolutionStore(settings.resolved_output_dir),
    )
