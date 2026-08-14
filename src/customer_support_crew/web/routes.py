"""The server-rendered console.

No build step and no external assets: `static/app.css` is the whole stylesheet and the
only JavaScript is the dozen inline lines that swap in the "running" state on submit.
That is what makes `uv run serve` the entire toolchain and lets the console work
offline. Keep it that way.

This router calls the use case directly, not the JSON API. It is a peer of the API,
not a layer on top of it.
"""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from customer_support_crew.api.deps import get_resolve_ticket_use_case
from customer_support_crew.core.errors import AppError
from customer_support_crew.features.support_triage.application.resolve_ticket import (
    ResolveTicketUseCase,
)
from customer_support_crew.features.support_triage.domain.policy import (
    ESCALATION_THRESHOLD,
)

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(tags=["console"])


def _render(request: Request, **context) -> HTMLResponse:
    context.setdefault("ticket_id", "")
    context.setdefault("result", None)
    context.setdefault("error", None)
    context.setdefault("escalated", False)
    context.setdefault("threshold", ESCALATION_THRESHOLD)
    return templates.TemplateResponse(request, "index.html", context)


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return _render(request)


@router.post("/resolve", response_class=HTMLResponse)
def resolve(
    request: Request,
    ticket_id: str = Form(...),
    use_case: ResolveTicketUseCase = Depends(get_resolve_ticket_use_case),
) -> HTMLResponse:
    """Run the crew for one ticket. Blocking on purpose — a run takes ~30s.

    FastAPI runs sync handlers in a threadpool, so a long run does not stall the event
    loop or other requests.

    Errors are caught here rather than left to the app-level handlers because those
    answer in JSON, and this endpoint owes the operator rendered HTML.
    """
    try:
        result = use_case.execute(ticket_id)
    except AppError as exc:
        return _render(request, ticket_id=ticket_id, error=str(exc))
    except Exception as exc:  # Jira auth, missing API keys, model errors
        return _render(
            request,
            ticket_id=ticket_id,
            error=f"The crew stopped on {ticket_id.strip().upper()}: {exc}",
        )

    payload = result.model_dump(mode="json")
    return _render(
        request,
        ticket_id=result.ticket_id,
        result=payload,
        escalated=result.escalated,
        raw_json=json.dumps(payload, indent=2, ensure_ascii=False),
    )
