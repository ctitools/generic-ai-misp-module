"""Offline tests for benchmarks/compare_summary.py on three synthetic reports."""

import csv
import json
from pathlib import Path

import pytest

from benchmarks import compare_summary

MD5 = "a" * 32
HEADINGS = ["## Threat", "## Targets", "## Indicators", "## Recommended actions"]
SUMMARY = "\n".join(HEADINGS) + f"\nThe dropper {MD5} beacons to 203.0.113.42 daily."
META = {"model": {"name": "m", "digest": "d", "server": "s"}, "prompt": {"cluster": "p"}}


def _dump(path: Path, obj) -> None:
    path.write_text(json.dumps(obj), encoding="utf-8")


@pytest.fixture(name="dirs")
def _dirs(tmp_path: Path) -> tuple[Path, Path, Path]:
    """A: ok, identical second pass; B: ok, second pass differs; C: gate error."""
    data, results, second = tmp_path / "data", tmp_path / "results", tmp_path / "pass2"
    for d in (data, results, second):
        d.mkdir()
    for uid in "abc":
        _dump(data / f"{uid}.json", {"id": uid, "title": f"Report {uid}"})
        _dump(
            results / f"{uid}.classic.json",
            {
                "indicators": [
                    ["md5", MD5],
                    ["ip-dst", "203.0.113.42"],
                    ["url", "http://x.example/"],
                ]
            },
        )
    _dump(results / "a.summary.json", META | {"summary": SUMMARY, "words": 9, "seconds": 1.0})
    _dump(results / "b.summary.json", META | {"summary": SUMMARY, "words": 9, "seconds": 2.0})
    _dump(
        results / "c.summary.json",
        {
            "error": "summary failed the structural check: missing heading '## Targets'; "
            "231 words > 200; indicator not in input: 10.0.0.1",
            "seconds": 3.0,
        },
    )
    _dump(second / "a.summary.json", META | {"summary": SUMMARY, "words": 9, "seconds": 1.0})
    _dump(
        second / "b.summary.json",
        META | {"summary": SUMMARY + " Also seen: more text here.", "words": 14, "seconds": 2.0},
    )
    return data, results, second


def test_report_and_csv(dirs: tuple[Path, Path, Path]) -> None:
    data, results, second = dirs
    out, csv_path = results / "r.md", results / "r.csv"
    args = ["--data-dir", str(data), "--results-dir", str(results), "--second-dir", str(second)]
    assert compare_summary.main([*args, "--out", str(out), "--csv", str(csv_path)]) == 0
    md = out.read_text(encoding="utf-8")
    assert "Reports: 3, summaries: 2, errors: 1." in md
    assert "| summary produced | 2 |" in md
    for kind in ("missing heading", "words >", "indicator not in input"):
        assert f"| {kind} | 1 |" in md
    assert "| 2 | 1 | " in md  # determinism: 2 paired, 1 byte-identical
    assert "| 2 | 0.667 | 0.667 |" in md  # coverage: md5 + ip of 3 classic values, 2 ok reports
    for block in ("pie title", "xychart-beta"):
        assert md.count(f"```mermaid\n{block}") >= 1
    with csv_path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert [r["status"] for r in rows] == ["ok", "ok", "error"]
    assert rows[0]["identical"] == "True" and rows[1]["identical"] == "False"


def test_helpers() -> None:
    assert compare_summary.gate_problems("LLM answer was truncated (max_tokens too small)") == [
        "LLM answer was truncated (max_tokens too"
    ]
    assert compare_summary.coverage("nothing", []) is None
    assert (
        compare_summary.coverage(f"hash {MD5.upper()}", [["md5", MD5], ["url", "http://a.b"]])
        == 0.5
    )
    assert compare_summary.similarity("a b c", "a b c") == 1.0
