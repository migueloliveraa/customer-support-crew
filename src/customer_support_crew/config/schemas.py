from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional

class ResolutionStatus(str, Enum):
    """The only two outcomes the resolver may return."""
    RESOLVED_DRAFT = "resolved_draft"
    ESCALATED_TO_HUMAN = "escalated_to_human"

class TicketTriageResult(BaseModel):
    """Schema for the Triage Agent's structured output."""
    ticket_id: str = Field(..., description="The unique identification key of the support ticket.")
    category: str = Field(..., description="Classification category (e.g., Technical, Billing, General Query).")
    frustration_score: int = Field(
        ..., ge=1, le=10,
        description=(
            "Customer frustration, calibrated strictly against these tiers. "
            "1-3: informational question or feature request; customer is not blocked and the tone is neutral or positive. "
            "4-6: customer is blocked or inconvenienced but stays civil; no anger, no threats, first or second contact. "
            "7-8: explicit anger or sarcasm, a repeated or ignored contact, or stated business impact. "
            "9-10: threat to churn or escalate legally, demand for a refund, or a report of data loss, "
            "a security problem, an unauthorized charge, or a total outage. "
            "FLOOR: if the ticket reports data loss, a security or access breach, an unauthorized or "
            "duplicate charge, or a complete outage, the score is never below 7 no matter how calm the "
            "wording. Otherwise judge tone, not severity. Most routine tickets belong in 1-6; reserve "
            "9-10 for the cases named above."
        ),
    )
    score_rationale: str = Field(
        ...,
        description=(
            "One or two sentences justifying the score, quoting the phrase from the ticket that drove it. "
            "If the score comes from the severity floor rather than the customer's tone, say so explicitly."
        ),
    )
    summary: str = Field(..., description="A concise structural summary of the issue reported by the customer.")

class TechnicalResolutionResult(BaseModel):
    """Schema for the Technical Resolver Agent's output."""
    ticket_id: str = Field(..., description="The unique identification key of the support ticket.")
    frustration_score: int = Field(
        ..., ge=1, le=10,
        description=(
            "The frustration_score from the triage analysis, copied verbatim. "
            "Do not re-score the ticket or adjust this number for any reason."
        ),
    )
    score_rationale: Optional[str] = Field(
        None, description="The score_rationale from the triage analysis, copied verbatim."
    )
    resolution_status: ResolutionStatus = Field(..., description="Outcome status: either 'resolved_draft' or 'escalated_to_human'.")
    email_response_template: Optional[str] = Field(None, description="The drafted customer reply if resolved. None if escalated.")
    internal_escalation_notes: Optional[str] = Field(None, description="Detailed technical handover notes if escalated.")