"""crewAI tool bindings.

Thin: the tool owns the agent-facing name, description and args schema; the actual
fetching lives behind a `TicketSource`, so the Jira client can be swapped for a fake in
tests without crewAI being involved.
"""

from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr

from customer_support_crew.features.support_triage.ports import TicketSource


class JiraTicketFetcherInput(BaseModel):
    """Input schema for fetching a Jira ticket."""

    ticket_key: str = Field(
        ..., description="The explicit Jira issue key to pull (e.g., 'SUP-101')."
    )


class JiraTicketFetcherTool(BaseTool):
    name: str = "Jira Ticket Fetcher Tool"
    description: str = (
        "Connects to a Jira instance and retrieves the summary and description of an issue key."
    )
    args_schema: Type[BaseModel] = JiraTicketFetcherInput

    # BaseTool is a pydantic model. The collaborator is a PrivateAttr rather than a
    # field so pydantic never tries to build a schema for the Protocol.
    _source: TicketSource = PrivateAttr()

    def __init__(self, source: TicketSource, **data) -> None:
        super().__init__(**data)
        self._source = source

    def _run(self, ticket_key: str) -> str:
        # Errors come back as tool output rather than as exceptions on purpose: the
        # agent sees the failure, can say so in its answer, and the run continues.
        return self._source.fetch(ticket_key)
