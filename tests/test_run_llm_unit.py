"""Offline tests for benchmarks/run_llm.py: the LLM is replaced by a canned answer."""

# pylint: disable=redefined-outer-name

import json

import pytest

from benchmarks import run_llm
from genai import llm

TEXT = "The dropper beacons to 203.0.113.42 and downloads from evil.example over HTTPS."
ANSWER = json.dumps(
    {
        "indicators": [
            {
                "type": "ip-dst",
                "value": "203.0.113.42",
                "quote": "to 203.0.113.42",
                "confidence": 1,
            },
            {
                "type": "domain",
                "value": "evil.example",
                "quote": "from evil.example",
                "confidence": 1,
            },
            {"type": "domain", "value": "nowhere.example", "quote": "x", "confidence": 1},
        ]
    }
)


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Two-entry orkl sample; OPENAI_MODEL set so main() gets past the settings check."""
    monkeypatch.setenv("OPENAI_MODEL", "fake-model")
    (tmp_path / "sample.json").write_text(json.dumps({"seed": 42, "n": 2, "ids": ["a", "b"]}))
    for uid in ("a", "b"):
        (tmp_path / f"{uid}.json").write_text(
            json.dumps({"id": uid, "title": f"Report {uid}", "plain_text": TEXT})
        )
    return tmp_path


@pytest.fixture
def fake_llm(monkeypatch):
    calls: list[str] = []

    def install(answer: str | Exception):
        def fake(messages, params, settings, json_mode=False):  # pylint: disable=unused-argument
            calls.append(messages[0]["content"])
            if isinstance(answer, Exception):
                raise answer
            return answer

        monkeypatch.setattr(llm, "llm_chat", fake)
        monkeypatch.setattr(llm, "is_reachable", lambda settings: True)
        monkeypatch.setattr(llm, "model_info", lambda settings: {"name": "fake-model"})
        return calls

    return install


def _args(data_dir, results_dir) -> list[str]:
    log_file = data_dir / "bench.log"
    return [
        "--data-dir",
        str(data_dir),
        "--results-dir",
        str(results_dir),
        "--log-file",
        str(log_file),
    ]


def test_writes_results_with_contract_keys(data_dir, tmp_path, fake_llm) -> None:
    calls = fake_llm(ANSWER)
    results = tmp_path / "results"
    assert run_llm.main(_args(data_dir, results)) == 0
    assert len(calls) == 2 and TEXT in calls[0]
    assert "done=2/2 ok=2 fail=0" in (data_dir / "bench.log").read_text()
    for uid in ("a", "b"):
        result = json.loads((results / f"{uid}.llm.json").read_text())
        assert set(result) == {"model", "prompt", "indicators", "rejected", "seconds"}
        assert result["model"] == {"name": "fake-model"}
        assert result["indicators"] == [["domain", "evil.example"], ["ip-dst", "203.0.113.42"]]
        assert [r["reason"] for r in result["rejected"]] == ["not-in-source"]
        assert isinstance(result["seconds"], float)


def test_llm_error_is_recorded_not_dropped(data_dir, tmp_path, fake_llm) -> None:
    fake_llm(llm.LLMError("boom"))
    results = tmp_path / "results"
    assert run_llm.main(_args(data_dir, results)) == 0
    result = json.loads((results / "a.llm.json").read_text())
    assert set(result) == {"error", "seconds"} and "boom" in result["error"]
    assert "fail=2" in (data_dir / "bench.log").read_text()


def test_pymisp_rejection_is_recorded_not_dropped(data_dir, tmp_path, fake_llm) -> None:
    # passes all five filters, but PyMISP refuses the value: an error file, not a crash
    (data_dir / "a.json").write_text(
        json.dumps({"id": "a", "title": "a", "plain_text": "first seen on not a date"})
    )
    candidate = {"type": "datetime", "value": "not a date", "quote": "not a date", "confidence": 1}
    fake_llm(json.dumps({"indicators": [candidate]}))
    results = tmp_path / "results"
    assert run_llm.main(_args(data_dir, results) + ["--ids", "a"]) == 0
    assert "error" in json.loads((results / "a.llm.json").read_text())


def test_second_run_skips_existing_unless_forced(data_dir, tmp_path, fake_llm) -> None:
    calls = fake_llm(ANSWER)
    args = _args(data_dir, tmp_path / "results")
    run_llm.main(args + ["--ids", "a"])
    run_llm.main(args)
    assert len(calls) == 2  # a, then only b
    run_llm.main(args + ["--force"])
    assert len(calls) == 4


def test_unreachable_llm_exits_2(data_dir, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(llm, "is_reachable", lambda settings: False)
    assert run_llm.main(_args(data_dir, tmp_path)) == 2
    assert not (tmp_path / "a.llm.json").exists()
