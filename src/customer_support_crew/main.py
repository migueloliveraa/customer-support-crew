#!/usr/bin/env python
import sys
import warnings

from customer_support_crew.pipeline import PipelineError, run_pipeline

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

DEFAULT_TICKET_ID = "CREWAISUP-10"


def run():
    """CLI entry point. Pass a ticket key as the first argument, or use the default."""
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    ticket_id = args[0] if args else DEFAULT_TICKET_ID

    print(f"[*] Starting Support Crew Pipeline processing Jira ticket: {ticket_id}...")

    try:
        result = run_pipeline(ticket_id)
    except PipelineError as exc:
        print(f"[FATAL ERROR] {exc}")
        return
    except Exception as exc:
        print(f"[FATAL ERROR] Execution failed: {exc}")
        return

    print("\n" + "=" * 40)
    print("          PIPELINE EXECUTION SUCCESS          ")
    print("=" * 40)

    score = result.get("frustration_score")
    if result.get("resolution_status") == "escalated_to_human":
        print(f"[ALERT] High Frustration Level detected ({score}/10)!")
        print("[STATUS] Ticket Escalated to Human Management Override Layer.")
        print(f"[NOTES] {result.get('internal_escalation_notes') or 'No notes provided.'}")
    else:
        print(f"[STATUS] Ticket successfully drafted by Tier-2 Engine ({score}/10).")
        print(f"[RESPONSE TEMPLATE]:\n{result.get('email_response_template') or 'No template generated.'}")


if __name__ == "__main__":
    run()
