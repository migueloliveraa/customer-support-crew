"""Construction of crewAI `LLM` objects.

The one rule here: never build an `LLM` at import time. Model strings come from the
environment, so building one in a class body means `os.getenv` runs when the module is
imported rather than when the crew is assembled — which is what made the old
`crew.py` fragile enough to need a hand-maintained import taboo.
"""

from crewai import LLM


def build_llm(model: str, temperature: float) -> LLM:
    """Build an LLM for a single agent. Call this from inside an `@agent` method."""
    return LLM(model=model, temperature=temperature)
