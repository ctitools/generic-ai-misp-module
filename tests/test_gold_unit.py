"""benchmarks/gold.py: gold sources become report-only events; results land in <dir>/gold."""

import json

from benchmarks import gold


def test_gold_sources_are_report_only() -> None:
    entries = gold.gold_events()
    assert set(entries) >= {"orkl-sample", "59ed4725-5f2a-4844-8dc4-e6926dbcb5ce"}
    for name, entry in entries.items():
        if "Event" in entry:
            assert set(entry["Event"]) == {"info", "EventReport"}, name  # no attributes leak in
            assert entry["Event"]["EventReport"], name
        else:
            assert entry["plain_text"].strip(), name


def test_main_writes_one_file_per_gold_report(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(gold, "run_one", lambda entry: {"indicators": [], "seconds": 0.1})
    assert gold.main(["--results-dir", str(tmp_path)]) == 0
    files = sorted(p.name for p in (tmp_path / "gold").glob("*.llm.json"))
    assert files == sorted(f"{n}.llm.json" for n in gold.gold_events())
    assert json.loads((tmp_path / "gold" / files[0]).read_text())["indicators"] == []
