"""Hand-computed checks for the pure metrics library used by the benchmarks."""

import pytest

from benchmarks import metrics as m


def test_normalise_value():
    assert m.normalise_value("  Evil.COM/ ") == "evil.com"
    assert m.normalise_value("a   b.") == "a b"
    assert m.values([("domain", "Evil.COM/"), ("hostname", "evil.com")]) == {"evil.com"}


def test_perfect_match():
    got = {"a", "b"}
    c = m.confusion(got, got)
    assert c == m.Confusion(tp=2, fp=0, fn=0, tn=0)
    s = m.scores(c)
    assert s["precision"] == s["recall"] == s["f1"] == s["jaccard"] == 1.0
    assert s["accuracy"] == 1.0
    assert s["specificity"] == 0.0  # no negatives in the universe
    assert m.cohen_kappa(got, got) == 1.0  # pe == po == 1.0


def test_disjoint_sets():
    c = m.confusion({"a"}, {"b"})
    assert c == m.Confusion(0, 1, 1, 0)
    assert all(v == 0.0 for v in m.scores(c).values())
    assert m.cohen_kappa({"a"}, {"b"}) <= 0.0


def test_one_sided_empty():
    c = m.confusion(set(), {"a", "b"})
    assert c == m.Confusion(0, 0, 2, 0)
    s = m.scores(c)
    assert s["precision"] == 0.0 and s["recall"] == 0.0 and s["jaccard"] == 0.0


def test_both_empty():
    c = m.confusion(set(), set())
    s = m.scores(c)
    assert s["precision"] == s["recall"] == s["jaccard"] == s["f1"] == 1.0
    assert s["accuracy"] == 0.0 and s["specificity"] == 0.0
    assert m.cohen_kappa(set(), set()) == 1.0


def test_wider_universe():
    c = m.confusion({"a", "b", "c"}, {"a", "b", "d"}, universe=set("abcdefgh"))
    assert c == m.Confusion(tp=2, fp=1, fn=1, tn=4)
    s = m.scores(c)
    assert s["specificity"] == pytest.approx(4 / 5)
    assert s["accuracy"] == pytest.approx(6 / 8)
    assert s["jaccard"] == pytest.approx(2 / 4)


def test_kappa_textbook():
    # tp=20, fp=5, fn=10, tn=15 -> po=0.7, pe=(25*30+25*20)/2500=0.5, kappa=0.4
    a = {f"tp{i}" for i in range(20)} | {f"fp{i}" for i in range(5)}
    b = {f"tp{i}" for i in range(20)} | {f"fn{i}" for i in range(10)}
    universe = a | b | {f"tn{i}" for i in range(15)}
    assert m.confusion(a, b, universe) == m.Confusion(20, 5, 10, 15)
    assert m.cohen_kappa(a, b, universe) == pytest.approx(0.4)


def test_aggregate_micro_vs_macro():
    per_report = [m.Confusion(1, 0, 0, 0), m.Confusion(0, 9, 1, 0)]
    agg = m.aggregate(per_report)
    assert agg["micro"]["precision"] == pytest.approx(1 / 10)
    assert agg["macro"]["precision"] == pytest.approx((1.0 + 0.0) / 2)
    assert m.aggregate([]) == {"micro": m.scores(m.Confusion(0, 0, 0, 0)), "macro": {}}


def test_by_type():
    got = [("ip-dst", "1.2.3.4"), ("domain", "Evil.com"), ("md5", "x")]
    ref = [("ip-src", "1.2.3.4"), ("hostname", "evil.com"), ("domain", "good.org")]
    assert m.by_type(got, ref) == {
        "ip-src": m.Confusion(1, 0, 0, 0),
        "hostname": m.Confusion(1, 0, 0, 0),
        "domain": m.Confusion(0, 0, 1, 0),
    }
