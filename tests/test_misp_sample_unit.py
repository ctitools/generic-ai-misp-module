"""Offline tests for benchmarks/misp_sample.py with a fake PyMISP client."""

import json
from pathlib import Path

import pytest

from benchmarks import misp_sample


class FakeMISP:
    def __init__(self, counts: dict[str, int]) -> None:
        self.counts, self.fetched = counts, []

    def search_index(self, pythonify=False):  # pylint: disable=unused-argument
        return [{"uuid": u, "attribute_count": str(n)} for u, n in self.counts.items()]

    def get_event(self, uuid, pythonify=False):  # pylint: disable=unused-argument
        self.fetched.append(uuid)
        return {"Event": {"uuid": uuid, "info": f"event {uuid}", "Attribute": []}}


def test_sample_filters_is_seeded_and_resumable(tmp_path: Path) -> None:
    misp = FakeMISP({"a": 1, "b": 7, "c": 50, "d": 400, "e": 12, "f": 5})
    ids = misp_sample.sample(misp, 3, 1, min_attributes=5, max_attributes=300, data_dir=tmp_path)
    assert len(ids) == 3 and set(ids) <= {"b", "c", "e", "f"}  # a (1) and d (400) excluded
    assert ids == misp_sample.sample(
        FakeMISP(misp.counts), 3, 1, min_attributes=5, max_attributes=300, data_dir=tmp_path
    )
    for uid in ids:
        assert json.loads((tmp_path / f"{uid}.json").read_text())["Event"]["uuid"] == uid
    meta = json.loads((tmp_path / "sample.json").read_text())
    assert meta["eligible"] == 4 and meta["library_events"] == 6 and meta["ids"] == ids
    again = FakeMISP(misp.counts)
    misp_sample.sample(again, 3, 1, min_attributes=5, max_attributes=300, data_dir=tmp_path)
    assert not again.fetched  # same parameters: reused without any fetch


def test_sample_refuses_when_too_few_eligible(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="only 1 eligible"):
        misp_sample.sample(
            FakeMISP({"a": 9}), 2, 1, min_attributes=5, max_attributes=300, data_dir=tmp_path
        )
