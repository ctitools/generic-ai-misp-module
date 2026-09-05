"""benchmarks/run_suggest.py with a fake suggest client and two events on disk."""

# pylint: disable=redefined-outer-name,unused-argument

import json

import pytest

from benchmarks import run_suggest
from genai import suggest


def test_score() -> None:
    gold = {"a:b", "c:d"}
    assert run_suggest.score(gold, ["a:b", "x:y"]) == {
        "precision": 0.5,
        "recall": 0.5,
        "hit_at_1": 1.0,
    }
    assert run_suggest.score(gold, []) == {"precision": 0.0, "recall": 0.0, "hit_at_1": 0.0}
    assert run_suggest.score(set(), ["a:b"])["recall"] == 0.0


def test_gold_tags_keeps_only_namespaced() -> None:
    event = {"Tag": [{"name": "tlp:amber"}, {"name": "plain"}, {"name": 'x:y="z"'}]}
    assert run_suggest.gold_tags(event) == {"tlp:amber", 'x:y="z"'}


def test_run_scores_and_records_failures(dummy_event, tmp_path, monkeypatch) -> None:
    good = dummy_event["Event"]
    bad = {**good, "uuid": "11111111-1111-4111-8111-111111111111", "info": "second"}
    for e in (good, bad):
        (tmp_path / f"{e['uuid']}.json").write_text(json.dumps({"Event": e}), encoding="utf-8")
    sent = []

    def fake(event, settings, limit=5, min_score=0.0):
        sent.append([t.name for t in event.tags])
        if event.info == "second":
            raise suggest.SuggestError("boom")
        event.add_tag("tlp:amber")
        return {"added": [{"tag": "tlp:amber", "score": 0.9}], "abstained": False}

    monkeypatch.setattr(suggest, "suggest_tags", fake)
    settings = suggest.SuggestSettings("http://s.example")
    result = run_suggest.run([good["uuid"], bad["uuid"]], tmp_path, settings, k=3)
    assert sent == [[], []]  # gold tags are stripped before the event is sent
    assert result["summary"]["events"] == 1 and result["summary"]["events_with_gold"] == 1
    assert result["summary"]["precision"] == 1.0 and result["summary"]["hit_at_1"] == 1.0
    assert result["summary"]["recall"] == pytest.approx(0.5)  # dummy event has two gold tags
    assert result["failures"] == [{"uuid": bad["uuid"], "error": "boom"}]
    assert result["events"][0]["gold"] == sorted(run_suggest.gold_tags(good))


def test_aggregate_empty() -> None:
    assert run_suggest.aggregate([])["events"] == 0
