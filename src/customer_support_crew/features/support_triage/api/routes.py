"""JSON API for the support-triage slice, mounted at /api/v1.

Handlers are sync `def` on purpose. FastAPI runs sync handlers in its threadpool, so
the ~30s blocking crew run does not stall the event loop or block other requests.

No try/except here: `InvalidTicketKey`, `PipelineError` and `ResolutionNotFound` are
mapped to status codes once, by the handlers registered in `api.app.create_app`.
"""

from fastapi import APIRouter, Depends

from customer_support_crew.api.deps import get_resolve_ticket_use_case
from customer_support_crew.features.support_triage.api.dto import (
    ConfigResponse,
    ResolutionResponse,
    ResolveRequest,
)
from customer_support_crew.features.support_triage.application.resolve_ticket import (
    ResolveTicketUseCase,
)
from customer_support_crew.features.support_triage.domain.models import ResolutionStatus
from customer_support_crew.features.support_triage.domain.policy import (
    ESCALATION_THRESHOLD,
)

router = APIRouter(prefix="/api/v1", tags=["support-triage"])


@router.post("/resolutions", response_model=ResolutionResponse)
def create_resolution(
    payload: ResolveRequest,
    use_case: ResolveTicketUseCase = Depends(get_resolve_ticket_use_case),
) -> ResolutionResponse:
    """Run the crew live for one ticket. Takes roughly 30 seconds."""
    return ResolutionResponse.from_domain(use_case.execute(payload.ticket_id))


@router.get("/resolutions/{ticket_id}", response_model=ResolutionResponse)
def read_resolution(
    ticket_id: str,
    use_case: ResolveTicketUseCase = Depends(get_resolve_ticket_use_case),
) -> ResolutionResponse:
    """The last stored resolution for a ticket. Does not run the crew."""
    return ResolutionResponse.from_domain(use_case.last_resolution(ticket_id))


@router.get("/config", response_model=ConfigResponse)
def read_config() -> ConfigResponse:
    """The policy constants a client needs to render a verdict."""
    return ConfigResponse(
        escalation_threshold=ESCALATION_THRESHOLD,
        resolution_statuses=[status.value for status in ResolutionStatus],
    )
