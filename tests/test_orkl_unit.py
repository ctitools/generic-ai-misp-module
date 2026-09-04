"""Offline tests for benchmarks/orkl.py against a fake orkl.eu library of six entries."""

# pytest fixtures are injected by name; pylint: disable=redefined-outer-name,unused-argument

import json

import pytest

from benchmarks import orkl

LIBRARY = [
    {"id": "a1", "language": "EN", "plain_text": "x" * 3000},  # orkl upper-cases it
    {"id": "b2", "language": "de", "plain_text": "x" * 3000},
    {"id": "c3", "language": "en", "plain_text": "x" * 100},
    {"id": "d4", "language": "en", "plain_text": "x" * 5000},
    {"id": "e5", "language": "en", "plain_text": "x" * 50000},
    {"id": "f6", "language": "en", "plain_text": "x" * 4000},
]
GOOD = {"a1", "d4", "f6"}


@pytest.fixture
def fake_api(monkeypatch):
    calls = []

    def _get(url):
        calls.append(url)
        if url.endswith("/library/info"):
            return {"data": {"library_entries": len(LIBRARY)}}
        if "/library/entries?" in url:
            params = dict(p.split("=") for p in url.split("?")[1].split("&"))
            offset, limit = int(params["offset"]), int(params["limit"])
            return {"data": LIBRARY[offset : offset + limit]}
        if "/library/entry/" in url:
            return {"data": next(e for e in LIBRARY if e["id"] == url.rsplit("/", 1)[1])}
        raise AssertionError(url)

    monkeypatch.setattr(orkl, "_get", _get)
    return calls


def test_sample_keeps_n_filtered_entries_and_writes_files(fake_api, tmp_path):
    ids = orkl.sample(n=2, seed=1, data_dir=tmp_path)
    assert len(ids) == 2 and set(ids) <= GOOD
    meta = json.loads((tmp_path / "sample.json").read_text())
    assert meta["ids"] == ids and meta["seed"] == 1 and meta["library_entries"] == 6
    for i in ids:
        assert json.loads((tmp_path / f"{i}.json").read_text())["id"] == i


def test_sample_is_deterministic_for_a_seed(fake_api, tmp_path):
    first = orkl.sample(n=3, seed=7, data_dir=tmp_path / "a")
    second = orkl.sample(n=3, seed=7, data_dir=tmp_path / "b")
    assert first == second and set(first) == GOOD


def test_sample_is_resumable(fake_api, tmp_path):
    ids = orkl.sample(n=2, seed=3, data_dir=tmp_path)
    fake_api.clear()
    assert orkl.sample(n=2, seed=3, data_dir=tmp_path) == ids
    assert not fake_api
    # different filters -> a fresh draw, not the cached one
    assert set(orkl.sample(n=2, seed=3, min_chars=4000, data_dir=tmp_path)) == {"d4", "f6"}
    assert fake_api


def test_sample_fails_when_library_too_small(fake_api, tmp_path):
    with pytest.raises(RuntimeError):
        orkl.sample(n=4, seed=1, data_dir=tmp_path)


def test_info_entry_entries(fake_api):
    assert orkl.info()["library_entries"] == 6
    assert orkl.entry("d4")["id"] == "d4"
    assert [e["id"] for e in orkl.entries(2, 1)] == ["b2", "c3"]
