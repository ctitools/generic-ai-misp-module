"""Compare the LLM IoC extraction against the classic regex extractor (and hand-labelled gold).

Reads ``benchmarks/data/orkl/sample.json`` plus the per-report ``*.classic.json`` /
``*.llm.json`` results and writes a GitHub-flavoured markdown report with Mermaid charts
and a csv. Matching is by normalised value only; indicator types are ignored on purpose.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
from collections import Counter
from dataclasses import astuple, dataclass
from datetime import date
from functools import cached_property
from pathlib import Path
from urllib.parse import urlparse

from benchmarks.metrics import (
    Confusion,
    aggregate,
    by_type,
    cohen_kappa,
    confusion,
    normalise_value,
    scores,
    values,
)

# --- loading -----------------------------------------------------------------------------------

TYPES = ["ip-dst", "url", "domain", "email", "md5", "sha1", "sha256", "sha512"]
URL_RE = re.compile(r"https?://[^\s\"'<>)]+")
CSV_COLUMNS = ["id", "title", "classic n", "llm n", "tp", "fp", "fn", "precision", "recall", "f1",
               "kappa", "seconds"]  # fmt: skip
METRICS = ["precision", "recall", "specificity", "accuracy", "f1", "jaccard"]


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def host_of(value: str) -> str:
    try:
        host = urlparse(value if "://" in value else "//" + value).hostname or ""
    except ValueError:  # defanged values such as evil[.]com are not urls
        return ""
    return host.removeprefix("www.")


def reporter_hosts(entry: dict) -> set[str]:
    """Hosts of the urls in sources / references / first line of the text: the reporting vendor."""
    texts = []
    for src in entry.get("sources") or []:
        texts += [
            v for v in (src.values() if isinstance(src, dict) else [src]) if isinstance(v, str)
        ]
    texts += [r for r in entry.get("references") or [] if isinstance(r, str)]
    texts.append((entry.get("plain_text") or "").split("\n", 1)[0])
    return {host_of(u) for t in texts for u in URL_RE.findall(t)} - {""}


@dataclass
class Report:
    id: str
    entry: dict
    classic: list
    llm: dict
    tool: str = "iocextract"

    @property
    def pairs(self) -> list:
        return self.llm.get("indicators", [])

    @cached_property
    def conf(self) -> Confusion:
        return confusion(values(self.pairs), values(self.classic))

    @cached_property
    def kappa(self) -> float:
        return cohen_kappa(values(self.pairs), values(self.classic))

    def row(self) -> list:
        s = scores(self.conf)
        title = (self.entry.get("title") or "")[:40]
        seconds = self.llm.get("seconds", 0.0)
        return [self.id, title, len(self.classic), len(self.pairs), *astuple(self.conf)[:3],
                s["precision"], s["recall"], s["f1"], self.kappa, seconds]  # fmt: skip


def load(data_dir: Path, results_dir: Path) -> tuple[dict, list[Report]]:
    sample, reports = _read(data_dir / "sample.json"), []
    for id_ in sample["ids"]:
        classic, llm = results_dir / f"{id_}.classic.json", results_dir / f"{id_}.llm.json"
        if classic.exists() and llm.exists():
            entry = data_dir / f"{id_}.json"
            entry = _read(entry) if entry.exists() else {}
            classic = _read(classic)
            reports.append(
                Report(id_, entry, classic["indicators"], _read(llm), classic.get("tool", "?"))
            )
    return sample, reports


# --- markdown helpers ----------------------------------------------------------------------------


def fmt(x) -> str:
    return f"{x:.3f}" if isinstance(x, float) else str(x)


def table(headers: list, rows: list[list]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(fmt(c) for c in r) + " |" for r in rows]
    return "\n".join(lines) + "\n"


def mermaid(body: str) -> str:
    return f"```mermaid\n{body}\n```\n"


def xychart(title: str, labels: list[str], series: dict[str, list], ymax=None) -> str:
    xs = ", ".join(f'"{x}"' for x in labels)
    ymax = ymax if ymax is not None else max([1] + [v for s in series.values() for v in s])
    bars = "\n".join(f"  bar [{', '.join(fmt(v) for v in s)}]" for s in series.values())
    axes = f'  x-axis [{xs}]\n  y-axis "{" / ".join(series)}" 0 --> {fmt(ymax)}'
    return mermaid(f'xychart-beta\n  title "{title}"\n{axes}\n{bars}')


def pie(title: str, items: dict[str, int]) -> str:
    return mermaid(f"pie title {title}\n" + "\n".join(f'  "{k}" : {v}' for k, v in items.items()))


def quadrant(reports: list[Report]) -> str:
    head = (
        "quadrantChart\n  title Reports by recall (x) and precision (y)\n"
        '  x-axis "low recall" --> "high recall"\n  y-axis "low precision" --> "high precision"\n'
        "  quadrant-1 agree\n  quadrant-2 LLM strict\n  quadrant-3 disagree\n"
        "  quadrant-4 LLM generous"
    )
    pts = [f"  {r.id[:8]}: [{fmt(scores(r.conf)['recall'])}, {fmt(scores(r.conf)['precision'])}]"
           for r in reports[:60]]  # fmt: skip
    return mermaid("\n".join([head, *pts]))


def f1_histogram(confs: list[Confusion]) -> str:
    f1s = [scores(c)["f1"] for c in confs]
    bins = [
        sum(1 for f in f1s if i / 10 <= f < (i + 1) / 10 or (i == 9 and f == 1.0))
        for i in range(10)
    ]
    return xychart("Per-report F1", [f"{i / 10:.1f}" for i in range(10)], {"reports": bins})


def count_chart(ok: list[Report], labels: list[str]) -> str:
    n_classic = Counter(t for r in ok for t, _ in r.classic)
    n_llm = Counter(t for r in ok for t, _ in r.pairs)
    series = {"classic": [n_classic[t] for t in labels], "llm": [n_llm[t] for t in labels]}
    return xychart("Indicators per type", labels, series)


def confusion_table(c: Confusion, cols: str) -> str:
    rows = [["LLM yes", c.tp, c.fp, c.tp + c.fp], ["LLM no", c.fn, c.tn, c.fn + c.tn]]
    rows.append(["total", c.tp + c.fn, c.fp + c.tn, sum(astuple(c))])
    return table(["", f"{cols} yes", f"{cols} no", "total"], rows)


def metrics_row(c: Confusion, kappa: float) -> list:
    return [*astuple(c), *(scores(c)[m] for m in METRICS), kappa]


# --- sections ------------------------------------------------------------------------------------


def header(sample: dict, reports: list[Report], ok: list[Report]) -> str:
    first = ok[0].llm if ok else {}
    model, prompt = first.get("model", {}), first.get("prompt", {})
    tool = reports[0].tool if reports else "iocextract"
    return f"""# Extraction benchmark: LLM vs classic regex extractor

Date: {date.today()}. Sample: seed {sample.get("seed")}, n {sample.get("n")}, reports with
results {len(reports)}, reports with LLM errors {len(reports) - len(ok)}.

- Model: `{model.get("name")}` digest `{model.get("digest")}` server `{model.get("server")}`
- Prompt: `{prompt.get("value")}` version `{prompt.get("version")}` sha256 `{prompt.get("sha256")}`
- Classic tool: `{tool}`

**Method.** Indicators are compared by normalised value only (lower-case, trailing `/` and `.`
stripped); types are ignored. The classic extractor is a deliberate *superset* reference (it also
catches defanged values), so an LLM "false positive" is a value the regexes missed and an LLM
"false negative" may be a correct omission (e.g. the reporting vendor's own site). Specificity and
accuracy need a wider universe than `llm ∪ classic` and are only meaningful in the gold view.
"""


def section_llm_vs_classic(ok: list[Report]) -> str:
    confs = [r.conf for r in ok]
    agg, micro_c = aggregate(confs), sum(confs, Confusion(0, 0, 0, 0))
    pooled_l = {f"{r.id}:{v}" for r in ok for v in values(r.pairs)}
    pooled_c = {f"{r.id}:{v}" for r in ok for v in values(r.classic)}
    metric_rows = [[m, agg["micro"][m], agg["macro"][m]] for m in METRICS]
    metric_rows.append(
        ["cohen_kappa", cohen_kappa(pooled_l, pooled_c), statistics.fmean(r.kappa for r in ok)]
    )
    types = {}  # by_type per report, then summed: the same value in two reports stays distinct
    for r in ok:
        for t, c in by_type(r.pairs, r.classic).items():
            types[t] = types.get(t, Confusion(0, 0, 0, 0)) + c
    types = dict(sorted(types.items()))
    labels = [t for t in TYPES if t in types] + sorted(set(types) - set(TYPES))
    agreement = {"LLM only": micro_c.fp, "both": micro_c.tp, "classic only": micro_c.fn}
    return (
        f"## LLM vs classic ({len(ok)} reports)\n\n### Confusion matrix (micro counts)\n\n"
        + confusion_table(micro_c, "classic")
        + "\n### Metrics\n\n"
        + table(["metric", "micro", "macro (mean per report)"], metric_rows)
        + "\n### Recall of classic values by type\n\n"
        + table(
            ["type", "classic n", "recall"],
            [[t, c.tp + c.fn, scores(c)["recall"]] for t, c in types.items()],
        )
        + xychart(
            "Recall by type", labels, {"recall": [scores(types[t])["recall"] for t in labels]}, 1.0
        )
        + "\n### Agreement\n\n"
        + pie("LLM-only / both / classic-only", agreement)
        + "\n### Per-report F1 histogram\n\n"
        + f1_histogram(confs)
        + "\n### Reports by recall and precision\n\n"
        + quadrant(ok)
        + "\n### Indicator counts per extractor\n\n"
        + count_chart(ok, labels)
        + "\n### Per report\n\n"
        + table(CSV_COLUMNS, [r.row() for r in ok])
    )


def section_deviations(ok: list[Report]) -> str:
    llm_only, classic_only, flags = [], [], Counter()
    for r in ok:
        llm, classic, hosts = values(r.pairs), values(r.classic), reporter_hosts(r.entry)
        llm_only += [[r.id[:8], t, v] for t, v in r.pairs if normalise_value(v) not in classic]
        for t, v in r.classic:
            if normalise_value(v) not in llm:
                flag = "reporter-domain" if host_of(v) in hosts else ""
                flags[flag or "other"] += 1
                classic_only.append([r.id[:8], t, v, flag])
    per_type, top = Counter(), []
    for x in sorted(classic_only, key=lambda x: x[1]):
        per_type[x[1]] += 1
        if per_type[x[1]] <= 10:
            top.append(x)
    reasons = Counter(x.get("reason", "?") for r in ok for x in r.llm.get("rejected", []))
    return (
        "## Deviations\n\n### LLM-only values (what the regexes missed), top 50\n\n"
        + table(["id", "type", "value"], llm_only[:50])
        + "\n### Classic-only values (what the LLM left out), first 10 per type\n\n"
        + f"reporter-domain: {flags['reporter-domain']}, other: {flags['other']} "
        f"(of {len(classic_only)} classic-only values)\n\n"
        + table(["id", "type", "value", "flag"], top[:50])
        + "\n### LLM rejection reasons (summed over reports)\n\n"
        + table(["reason", "count"], sorted(reasons.items(), key=lambda x: -x[1]))
    )


def section_gold(gold_dir: Path, results_dir: Path) -> str:
    rows, kappas = [], []
    pooled = {k: set() for k in ("llm", "classic", "gold", "universe")}
    for gold_file in sorted(gold_dir.glob("*.iocs.json")):
        name = gold_file.name.removesuffix(".iocs.json")
        files = {k: results_dir / f"{name}.{k}.json" for k in ("classic", "llm")}
        if not all(f.exists() for f in files.values()):
            continue
        sets = {k: values(_read(f).get("indicators", [])) for k, f in files.items()}
        sets["gold"] = values(_read(gold_file)["indicators"])
        sets["universe"] = set().union(*sets.values())
        for k, s in sets.items():
            pooled[k] |= {f"{name}:{v}" for v in s}
        for who in ("llm", "classic"):
            c = confusion(sets[who], sets["gold"], sets["universe"])
            rows.append(
                [
                    name[:8],
                    f"{who} vs gold",
                    *metrics_row(c, cohen_kappa(sets[who], sets["gold"], sets["universe"])),
                ]
            )
        pairs = (("llm", "gold"), ("classic", "gold"), ("llm", "classic"))
        kappas.append(
            [name[:8], *(cohen_kappa(sets[a], sets[b], sets["universe"]) for a, b in pairs)]
        )
    if not rows:
        return ""
    for who in ("llm", "classic"):
        c = confusion(pooled[who], pooled["gold"], pooled["universe"])
        rows.append(
            [
                "micro",
                f"{who} vs gold",
                *metrics_row(c, cohen_kappa(pooled[who], pooled["gold"], pooled["universe"])),
            ]
        )
    return (
        f"## Gold view ({len(kappas)} hand-labelled reports)\n\nUniverse = classic ∪ llm ∪ gold "
        "per report, so tn, specificity and accuracy are meaningful.\n\n"
        + table(["report", "pair", "tp", "fp", "fn", "tn", *METRICS, "kappa"], rows)
        + "\n### Cohen's kappa\n\n"
        + table(["report", "LLM–gold", "classic–gold", "LLM–classic"], kappas)
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", type=Path, default=Path("benchmarks/data/orkl"))
    ap.add_argument("--results-dir", type=Path, default=Path("benchmarks/results"))
    ap.add_argument("--gold-dir", type=Path, default=Path("fixtures/gold"))
    ap.add_argument("--out", type=Path, default=Path("docs/BENCHMARKS_extraction.md"))
    ap.add_argument("--csv", type=Path, default=Path("benchmarks/results/extraction.csv"))
    args = ap.parse_args(argv)
    sample, reports = load(args.data_dir, args.results_dir)
    ok = [r for r in reports if "indicators" in r.llm]
    body = section_llm_vs_classic(ok) if ok else "## LLM vs classic\n\nNo results.\n"
    gold_results = args.results_dir / "gold"
    gold = section_gold(args.gold_dir, gold_results) if gold_results.is_dir() else ""
    reproduce = (
        "## Reproduce\n\n```bash\npython -m benchmarks.orkl --n 100 --seed 42\n"
        "python -m genai.classic benchmarks/data/orkl/*.json -o benchmarks/results\n"
        f"python -m benchmarks.run_llm\npython -m benchmarks.compare --data-dir {args.data_dir} "
        f"--results-dir {args.results_dir} --out {args.out} --csv {args.csv}\n```\n"
    )
    parts = [header(sample, reports, ok), body, section_deviations(ok), gold, reproduce]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(p for p in parts if p), encoding="utf-8")
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows([CSV_COLUMNS, *(r.row() for r in ok)])
    print(f"wrote {args.out} and {args.csv} ({len(ok)} reports)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
