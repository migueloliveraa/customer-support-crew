#!/usr/bin/env python
"""CLI client of the support-triage slice: `uv run run_crew CREWAISUP-3`."""

import sys
import warnings

from customer_support_crew.api.deps import get_resolve_ticket_use_case
from customer_support_crew.core.errors import AppError

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

DEFAULT_TICKET_ID = "CREWAISUP-10"


def run() -> None:
    """Pass a ticket key as the first argument, or use the default."""
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    ticket_id = args[0] if args else DEFAULT_TICKET_ID

    print(f"[*] Starting Support Crew Pipeline processing Jira ticket: {ticket_id}...")

    try:
        result = get_resolve_ticket_use_case().execute(ticket_id)
    except AppError as exc:
        print(f"[FATAL ERROR] {exc}")
        return
    except Exception as exc:
        print(f"[FATAL ERROR] Execution failed: {exc}")
        return

    print("\n" + "=" * 40)
    print("          PIPELINE EXECUTION SUCCESS          ")
    print("=" * 40)

    if result.escalated:
        print(f"[ALERT] High Frustration Level detected ({result.frustration_score}/10)!")
        print("[STATUS] Ticket Escalated to Human Management Override Layer.")
        print(f"[NOTES] {result.internal_escalation_notes or 'No notes provided.'}")
    else:
        print(
            f"[STATUS] Ticket successfully drafted by Tier-2 Engine "
            f"({result.frustration_score}/10)."
        )
        print(
            f"[RESPONSE TEMPLATE]:\n"
            f"{result.email_response_template or 'No template generated.'}"
        )


if __name__ == "__main__":
    run()
