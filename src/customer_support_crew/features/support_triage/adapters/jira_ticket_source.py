"""`TicketSource` backed by Atlassian Jira Cloud.

Failures come back as strings rather than exceptions — see the `TicketSource` docstring
in `ports.py` for why. This module holds all the Jira specifics; the crewAI tool that
calls it knows only the port.
"""

from jira import JIRA

from customer_support_crew.core.settings import Settings, get_settings


class JiraTicketSource:
    """Fetches summary + description for an issue key over Jira Cloud basic auth."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def fetch(self, ticket_key: str) -> str:
        settings = self._settings
        if not settings.has_jira_credentials():
            return "Error: Missing Jira configuration environment variables."

        try:
            client = JIRA(
                server=settings.jira_server_url,
                basic_auth=(
                    settings.jira_email,
                    settings.jira_api_token.get_secret_value(),
                ),
            )
            issue = client.issue(ticket_key)

            summary = issue.fields.summary
            description = issue.fields.description or "No description provided."

            return (
                f"Ticket Key: {ticket_key}\n"
                f"Summary: {summary}\n"
                f"Description: {description}"
            )
        except Exception as exc:  # noqa: BLE001 — reported to the agent, not raised
            return f"Failed to fetch ticket {ticket_key} from Jira. Error: {exc}"
