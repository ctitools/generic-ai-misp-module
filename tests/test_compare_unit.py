"""Offline tests for benchmarks/compare.py on three synthetic reports."""

import csv
import json
from pathlib import Path

import pytest

from benchmarks import compare

MD5 = "a" * 32
IDS = ["aaaaaaaa-0001", "bbbbbbbb-0002", "cccccccc-0003"]
LLM_META = {
    "model": {"name": "m", "digest": "d", "server": "s"},
    "prompt": {"value": "p", "uuid": "u", "version": "1", "sha256": "h"},
}


def _dump(path: Path, obj) -> None:
    path.write_text(json.dumps(obj), encoding="utf-8")


@pytest.fixture(name="data")
def _data(tmp_path: Path) -> Path:
    """A: 2 tp, 1 llm-only, 1 classic-only (a reporter-domain value); B: 1 tp; C: LLM error."""
    data, results = tmp_path / "data", tmp_path / "results"
    data.mkdir()
    results.mkdir()
    _dump(data / "sample.json", {"seed": 1, "n": 3, "ids": IDS})
    entries = {
        IDS[0]: {"title": "Report A" * 10, "references": ["https://www.vendor.example/blog"]},
        IDS[1]: {"title": "B", "sources": [{"url": "https://other.example/x"}]},
        IDS[2]: {"title": "C", "plain_text": "see https://c.example\nbody"},
    }
    classic = {
        IDS[0]: [["url", "http://evil.com/x"], ["md5", MD5], ["domain", "vendor.example"]],
        IDS[1]: [["domain", "bad.org"]],
        IDS[2]: [["ip-dst", "1.2.3.4"]],
    }
    llm = {
        IDS[0]: {
            "indicators": [
                ["url", "http://evil.com/x/"],
                ["md5", MD5.upper()],
                ["ip-dst", "9.9.9.9"],
            ]
        },
        IDS[1]: {"indicators": [["domain", "bad.org"]], "rejected": [{"reason": "not in source"}]},
        IDS[2]: {"error": "timeout"},
    }
    for id_ in IDS:
        _dump(data / f"{id_}.json", entries[id_] | {"id": id_})
        _dump(
            results / f"{id_}.classic.json",
            {"tool": "iocextract 1.16.1", "indicators": classic[id_]},
        )
        _dump(results / f"{id_}.llm.json", LLM_META | llm[id_] | {"seconds": 1.5})
    return tmp_path


def _run(data: Path) -> tuple[str, list[dict]]:
    out, csv_path = data / "report.md", data / "r.csv"
    args = ["--data-dir", str(data / "data"), "--results-dir", str(data / "results")]
    assert compare.main([*args, "--out", str(out), "--csv", str(csv_path)]) == 0
    with csv_path.open(encoding="utf-8") as fh:
        return out.read_text(encoding="utf-8"), list(csv.DictReader(fh))


def test_report_contents(data: Path) -> None:
    md, rows = _run(data)
    for word in ("precision", "recall", "specificity", "accuracy", "f1", "jaccard", "cohen_kappa"):
        assert word in md
    assert "| LLM yes | 3 | 1 | 4 |" in md and "| LLM no | 1 | 0 | 1 |" in md
    for block in ("xychart-beta", "pie title", "quadrantChart"):
        assert md.count(f"```mermaid\n{block}") >= 1
    assert "| vendor.example | reporter-domain |" in md and "reporter-domain: 1, other: 0" in md
    assert "| domain | 2 | 0.500 |" in md  # recall by type: vendor.example missed, bad.org found
    assert "| not in source | 1 |" in md
    assert "reports with LLM errors 1" in md and "iocextract 1.16.1" in md
    assert "Gold view" not in md
    assert [r["id"] for r in rows] == IDS[:2]  # the errored report has no per-report row


def test_micro_f1_hand_computed(data: Path) -> None:
    md, rows = _run(data)
    # micro: tp=3 (evil url, md5, bad.org), fp=1 (9.9.9.9), fn=1 (vendor.example) -> P=R=F1=0.75
    # macro: report A f1 = 2*2/(4+1+1) = 0.667, report B f1 = 1 -> mean 0.833
    assert "| f1 | 0.750 | 0.833 |" in md
    assert rows[0]["f1"].startswith("0.666") and rows[0]["title"] == ("Report A" * 10)[:40]


def test_gold_view(data: Path) -> None:
    gold_dir, gold_results = data / "gold", data / "results" / "gold"
    gold_dir.mkdir()
    gold_results.mkdir()
    _dump(gold_dir / "x.iocs.json", {"indicators": [["md5", MD5], ["domain", "bad.org"]]})
    _dump(
        gold_results / "x.classic.json",
        {"indicators": [["md5", MD5], ["domain", "vendor.example"]]},
    )
    _dump(gold_results / "x.llm.json", {"indicators": [["md5", MD5], ["domain", "bad.org"]]})
    out = data / "g.md"
    args = ["--data-dir", str(data / "data"), "--results-dir", str(data / "results")]
    compare.main([*args, "--gold-dir", str(gold_dir), "--out", str(out), "--csv", str(data / "g")])
    md = out.read_text(encoding="utf-8")
    # universe = {md5, bad.org, vendor.example}: llm tp2 fp0 fn0 tn1; classic tp1 fp1 fn1 tn0
    ones = " | ".join(["1.000"] * 7)
    assert f"| x | llm vs gold | 2 | 0 | 0 | 1 | {ones} |" in md
    assert "| x | classic vs gold | 1 | 1 | 1 | 0 |" in md


def test_helpers() -> None:
    assert compare.host_of("https://www.vendor.example/blog") == "vendor.example"
    assert compare.host_of("vendor.example") == "vendor.example"
    assert compare.host_of("hxxp://evil[.]com/x") == ""  # defanged: no crash, no host
