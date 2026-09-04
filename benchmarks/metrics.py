"""Pure set-based metrics for comparing indicator extractors (stdlib only).

Matching is by *value* only: types are ignored on purpose, because ip-src vs ip-dst or
domain vs hostname are typing choices, not extraction errors. Degenerate denominators give
0.0, except precision/recall/jaccard (and hence f1) when both sets are empty, which give 1.0:
perfect agreement on nothing.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import astuple, dataclass
from statistics import mean


@dataclass(frozen=True)
class Confusion:
    tp: int
    fp: int
    fn: int
    tn: int

    def __add__(self, other: "Confusion") -> "Confusion":
        return Confusion(*(a + b for a, b in zip(astuple(self), astuple(other), strict=True)))


_REFANG = (("hxxp", "http"), ("[.]", "."), ("(.)", "."), ("[:]", ":"), ("[at]", "@"), ("[@]", "@"))


def normalise_value(value: str) -> str:
    """Lower-case, whitespace-collapsed, refanged, trailing `/` and `.` stripped."""
    value = " ".join(value.lower().split())
    for defanged, plain in _REFANG:
        value = value.replace(defanged, plain)
    return value.rstrip("/.")


def values(indicators: Iterable[tuple[str, str]]) -> set[str]:
    return {normalise_value(value) for _, value in indicators}


def confusion(got: set[str], ref: set[str], universe: set[str] | None = None) -> Confusion:
    """Counts against a universe of candidate items (default got | ref, so tn == 0)."""
    tn = len(universe - got - ref) if universe is not None else 0
    return Confusion(len(got & ref), len(got - ref), len(ref - got), tn)


def _ratio(num: float, den: float, empty: float = 0.0) -> float:
    return num / den if den else empty


def scores(c: Confusion) -> dict[str, float]:
    nothing = 1.0 if c.tp + c.fp + c.fn == 0 else 0.0
    recall = _ratio(c.tp, c.tp + c.fn, nothing)
    return {
        "precision": _ratio(c.tp, c.tp + c.fp, nothing),
        "recall": recall,
        "sensitivity": recall,
        "specificity": _ratio(c.tn, c.tn + c.fp),
        "accuracy": _ratio(c.tp + c.tn, c.tp + c.fp + c.fn + c.tn),
        "f1": _ratio(2 * c.tp, 2 * c.tp + c.fp + c.fn, nothing),
        "jaccard": _ratio(c.tp, c.tp + c.fp + c.fn, nothing),
    }


def cohen_kappa(a: set[str], b: set[str], universe: set[str] | None = None) -> float:
    """Two raters marking each item of the universe as present/absent."""
    c = confusion(a, b, universe if universe is not None else a | b)
    n = c.tp + c.fp + c.fn + c.tn
    if n == 0:
        return 1.0
    po = (c.tp + c.tn) / n
    pe = ((c.tp + c.fp) * (c.tp + c.fn) + (c.fn + c.tn) * (c.fp + c.tn)) / (n * n)
    if pe == 1.0:
        return 1.0 if po == 1.0 else 0.0
    return (po - pe) / (1 - pe)


def aggregate(per_report: list[Confusion]) -> dict[str, dict[str, float]]:
    """micro = scores of summed counts; macro = mean of per-report scores."""
    micro = scores(sum(per_report, Confusion(0, 0, 0, 0)))
    per_scores = [scores(c) for c in per_report]
    macro = {k: mean(s[k] for s in per_scores) for k in micro} if per_scores else {}
    return {"micro": micro, "macro": macro}


def by_type(got: Iterable[tuple[str, str]], ref: Iterable[tuple[str, str]]) -> dict[str, Confusion]:
    """Per reference type: the ref pair's type decides the bucket, got is matched by value.

    Got-only values have no reference type, so they land in no bucket: per-type fp is always
    0 and only recall is meaningful here. Use confusion()/scores() on the whole sets for fp.
    """
    ref_by_type: dict[str, set[str]] = defaultdict(set)
    for kind, value in ref:
        ref_by_type[kind].add(normalise_value(value))
    got_values = values(got)
    return {kind: confusion(got_values & refs, refs) for kind, refs in ref_by_type.items()}
