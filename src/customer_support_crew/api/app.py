"""FastAPI application factory.

Two clients of the same use case are mounted here and neither is layered on the other:
the JSON API at `/api/v1` and the server-rendered console at `/`. The console calls the
use case directly rather than its own HTTP endpoint — no self-request round-trip, and
it keeps working if the API is ever unmounted.
"""

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from customer_support_crew.core.errors import (
    InvalidTicketKey,
    PipelineError,
    ResolutionNotFound,
)
from customer_support_crew.features.support_triage.api.routes import (
    router as support_triage_router,
)
from customer_support_crew.web.routes import STATIC_DIR
from customer_support_crew.web.routes import router as web_router

logger = logging.getLogger(__name__)

# Flipped by the warm-up thread; reported by /health so a slow first request is
# explainable rather than mysterious.
_warm = threading.Event()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Import the crew in the background while the operator is still typing.

    Without this the first submit of the process pays ~10s of crewai/litellm import on
    top of the run itself, which reads as "the first ticket is slow". On a daemon thread
    so the server accepts connections immediately and Ctrl-C is not held up; a submit
    arriving mid-import simply blocks on the same import lock and is no worse off.
    """

    def _warm_up() -> None:
        from customer_support_crew.features.support_triage.adapters.crewai_pipeline.pipeline import (
            warm_up,
        )

        try:
            warm_up()
        finally:
            _warm.set()

    threading.Thread(target=_warm_up, name="crew-warmup", daemon=True).start()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Support Crew Console", lifespan=lifespan)

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(support_triage_router)
    app.include_router(web_router)

    _register_exception_handlers(app)

    @app.get("/health", tags=["ops"])
    def health() -> dict:
        return {"status": "ok", "crew_warm": _warm.is_set()}

    return app


def _register_exception_handlers(app: FastAPI) -> None:
    """Map the application's error vocabulary onto status codes, once.

    Both the JSON API and the web console inherit this, which is why neither has a
    stack of `except` clauses. The web router still catches for itself, because it has
    to answer with rendered HTML rather than JSON.
    """

    @app.exception_handler(InvalidTicketKey)
    def _invalid_key(request: Request, exc: InvalidTicketKey) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(ResolutionNotFound)
    def _not_found(request: Request, exc: ResolutionNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(PipelineError)
    def _pipeline_failed(request: Request, exc: PipelineError) -> JSONResponse:
        logger.exception("Pipeline failure on %s", request.url.path)
        return JSONResponse(status_code=502, content={"detail": str(exc)})


app = create_app()


def main() -> None:
    """Console-script entry point: `uv run serve`."""
    import uvicorn

    uvicorn.run(
        "customer_support_crew.api.app:app", host="127.0.0.1", port=8000, reload=False
    )


if __name__ == "__main__":
    main()
