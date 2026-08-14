"""The error vocabulary every layer shares.

These are mapped to HTTP status codes once, in `api.app.create_app`, so neither the
route handlers nor the use case has to know about HTTP.
"""


class AppError(Exception):
    """Base class for every failure this application raises deliberately."""


class InvalidTicketKey(AppError, ValueError):
    """The supplied string is not shaped like a Jira issue key.

    Raised before any LLM call is made, so a typo costs nothing.
    """


class PipelineError(AppError, RuntimeError):
    """The crew ran but did not return a resolution we could parse or validate."""


class ResolutionNotFound(AppError, LookupError):
    """No stored resolution exists for the requested ticket."""
