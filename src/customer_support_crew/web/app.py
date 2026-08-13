"""FastAPI front end for the support crew.

Server-rendered, no build step and no external assets: the browser posts a form,
the request thread runs the crew live, and the same template renders the verdict.
"""

import json
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from customer_support_crew.pipeline import (
    ESCALATION_THRESHOLD,
    InvalidTicketKey,
    PipelineError,
    ResolutionStatus,
    run_pipeline,
    warm_up,
)

BASE_DIR = Path(__file__).parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Import the crew in the background while the operator is still typing.

    Without this the first submit of the process pays ~10s of crewai/litellm import
    on top of the run itself, which reads as "the first ticket is slow". On a daemon
    thread so the server starts accepting connections immediately and Ctrl-C is not
    held up; a submit arriving mid-import simply blocks on the same import lock and
    is no worse off than before.
    """
    threading.Thread(target=warm_up, name="crew-warmup", daemon=True).start()
    yield


app = FastAPI(title="Support Crew Console", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _render(request: Request, **context) -> HTMLResponse:
    context.setdefault("ticket_id", "")
    context.setdefault("result", None)
    context.setdefault("error", None)
    context.setdefault("escalated", False)
    context.setdefault("threshold", ESCALATION_THRESHOLD)
    return templates.TemplateResponse(request, "index.html", context)


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return _render(request)


@app.post("/resolve", response_class=HTMLResponse)
def resolve(request: Request, ticket_id: str = Form(...)) -> HTMLResponse:
    """Run the crew for one ticket. Blocking on purpose — a run takes ~30s.

    FastAPI runs sync handlers in a threadpool, so a long run does not stall the
    event loop or other requests.
    """
    try:
        result = run_pipeline(ticket_id)
    except InvalidTicketKey as exc:
        return _render(request, ticket_id=ticket_id, error=str(exc))
    except PipelineError as exc:
        return _render(request, ticket_id=ticket_id, error=str(exc))
    except Exception as exc:  # Jira auth, missing API keys, model errors
        return _render(
            request,
            ticket_id=ticket_id,
            error=f"The crew stopped on {ticket_id.strip().upper()}: {exc}",
        )

    return _render(
        request,
        ticket_id=result.get("ticket_id", ticket_id),
        result=result,
        escalated=result.get("resolution_status") == ResolutionStatus.ESCALATED_TO_HUMAN,
        raw_json=json.dumps(result, indent=2, ensure_ascii=False),
    )


def main():
    """Console-script entry point: `uv run serve`."""
    import uvicorn

    uvicorn.run("customer_support_crew.web.app:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
