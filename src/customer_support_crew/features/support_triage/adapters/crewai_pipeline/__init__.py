"""The crewAI implementation of `TriagePipeline`.

Importing this package sets `CREWAI_DISABLE_TELEMETRY` before crewAI itself is
imported. crewAI ships anonymous OpenTelemetry tracing that POSTs to
telemetry.crewai.com:4319 on every run; export failures are caught, but the exporter
retries with backoff and logs a wall of "Transient error … retrying" whenever a
firewall or antivirus blocks the connection. `setdefault` so an explicit value in
`.env` or the shell still wins if someone wants the traces back.

The package is named `crewai_pipeline` rather than `crewai` on purpose: a subpackage
called `crewai` would shadow the real library for absolute imports inside it.
"""

import os

# Imported first so `load_dotenv()` has run: `setdefault` below must not win over a
# CREWAI_DISABLE_TELEMETRY that the operator put in `.env`.
from customer_support_crew.core import settings as _settings  # noqa: F401

os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
