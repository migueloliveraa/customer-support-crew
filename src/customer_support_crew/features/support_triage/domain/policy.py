"""The escalation policy: the one place the number 7 is written down.

Escalation stays *prompt-encoded* — there is no Python branch that overrides the
resolver's decision, and adding one is not the intent here. What changed is that the
threshold is no longer typed three times (prompt prose, gauge marker, score
calibration floor). It is defined once, here, and reaches:

* `config/tasks.yaml`, via the `{escalation_threshold}` placeholder that
  `CrewAITriagePipeline` fills from the `kickoff()` inputs dict;
* `domain/models.py`, which builds the severity-floor sentence of the
  `frustration_score` field description from it;
* the web console gauge and `GET /api/v1/config`.

Change the constant and all four move together.
"""

ESCALATION_THRESHOLD = 7


def should_escalate(frustration_score: int) -> bool:
    """What the policy says the outcome ought to be for a given score.

    This is *not* enforcement. The resolver agent decides the actual
    `resolution_status`; the use case calls this only to notice when the model
    disagreed with the stated rule and to log that fact.
    """
    return frustration_score >= ESCALATION_THRESHOLD
