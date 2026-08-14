"""`ResolutionStore` backed by JSON files under `output/`.

This replaces the crewAI task's `output_file=` parameter. That parameter took a
*relative* path, which meant results landed wherever the process happened to be
started; writing here instead lets the path come from `Settings.resolved_output_dir`,
which is anchored to the repository root. Same filenames, same JSON, no CWD coupling.
"""

import json
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from customer_support_crew.features.support_triage.domain.models import (
    TechnicalResolutionResult,
)

FILENAME_TEMPLATE = "final_resolution__{ticket_id}.json"


class FileResolutionStore:
    def __init__(self, output_dir: Path) -> None:
        self._output_dir = Path(output_dir)

    def path_for(self, ticket_key: str) -> Path:
        return self._output_dir / FILENAME_TEMPLATE.format(ticket_id=ticket_key)

    def save(self, result: TechnicalResolutionResult) -> Path:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        path = self.path_for(result.ticket_id)
        payload = result.model_dump(mode="json")
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return path

    def load(self, ticket_key: str) -> Optional[TechnicalResolutionResult]:
        path = self.path_for(ticket_key)
        if not path.exists():
            return None
        try:
            return TechnicalResolutionResult.model_validate_json(
                path.read_text(encoding="utf-8")
            )
        except (ValidationError, ValueError):
            # A stored file that no longer matches the schema is treated as absent
            # rather than crashing a read; the caller can always re-run the ticket.
            return None
