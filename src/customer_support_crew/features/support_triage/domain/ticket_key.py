"""Jira issue key validation, so a typo fails before it costs an LLM call."""

import re

from customer_support_crew.core.errors import InvalidTicketKey

TICKET_KEY_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9]*-\d+$")


def normalize_ticket_id(raw: str) -> str:
    """Uppercase and validate a Jira key, or raise `InvalidTicketKey`."""
    ticket_id = (raw or "").strip().upper()
    if not TICKET_KEY_PATTERN.match(ticket_id):
        raise InvalidTicketKey(
            f"'{raw}' is not a Jira issue key. Use a key like CREWAISUP-10."
        )
    return ticket_id
