from customer_support_crew.features.support_triage.adapters.file_resolution_store import (
    FileResolutionStore,
)
from customer_support_crew.features.support_triage.domain.models import ResolutionStatus

from tests.conftest import make_result


def test_round_trips_and_keeps_the_historical_filename(tmp_path):
    store = FileResolutionStore(tmp_path / "output")
    result = make_result(
        ticket_id="CREWAISUP-6",
        frustration_score=9,
        status=ResolutionStatus.ESCALATED_TO_HUMAN,
    )

    path = store.save(result)

    assert path.name == "final_resolution__CREWAISUP-6.json"
    assert store.load("CREWAISUP-6") == result


def test_missing_and_corrupt_files_read_as_absent(tmp_path):
    store = FileResolutionStore(tmp_path)
    assert store.load("CREWAISUP-1") is None

    store.path_for("CREWAISUP-1").write_text("{not json", encoding="utf-8")
    assert store.load("CREWAISUP-1") is None
