"""The seams of the slice.

The application layer depends only on these Protocols, never on Jira, the filesystem,
or crewAI. That is what lets the test suite run the whole use case — and the whole web
console — with no API key and no network.
"""

from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

from customer_support_crew.features.support_triage.domain.models import (
    TechnicalResolutionResult,
)


@runtime_checkable
class TicketSource(Protocol):
    """Where ticket text comes from."""

    def fetch(self, ticket_key: str) -> str:
        """Return the ticket as text.

        Implementations report failure as a *returned string*, not an exception. The
        crewAI tool that wraps this hands the return value straight to the agent, and
        an agent that sees "Failed to fetch…" as tool output can keep going and say so
        in its answer. Raising would abort the run instead.
        """


@runtime_checkable
class TriagePipeline(Protocol):
    """Whatever actually scores the ticket and produces a resolution."""

    def run(self, ticket_key: str) -> TechnicalResolutionResult: ...


@runtime_checkable
class ResolutionStore(Protocol):
    """Where finished resolutions are kept."""

    def save(self, result: TechnicalResolutionResult) -> Path: ...

    def load(self, ticket_key: str) -> Optional[TechnicalResolutionResult]:
        """Return the last stored resolution for a ticket, or None."""
