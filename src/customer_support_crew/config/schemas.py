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
    frustration_score: int = Field(..., description="An emotional frustration level scaled integer from 1 to 10.")
    summary: str = Field(..., description="A concise structural summary of the issue reported by the customer.")

class TechnicalResolutionResult(BaseModel):
    """Schema for the Technical Resolver Agent's output."""
    ticket_id: str = Field(..., description="The unique identification key of the support ticket.")
    frustration_score: int = Field(..., description="The frustration score transferred from triage.")
    resolution_status: ResolutionStatus = Field(..., description="Outcome status: either 'resolved_draft' or 'escalated_to_human'.")
    email_response_template: Optional[str] = Field(None, description="The drafted customer reply if resolved. None if escalated.")
    internal_escalation_notes: Optional[str] = Field(None, description="Detailed technical handover notes if escalated.")