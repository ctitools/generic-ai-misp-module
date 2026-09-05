"""Unit tests for genai/classic.py, the regex (iocextract) superset baseline used by benchmarks."""

import json
from pathlib import Path

from genai.classic import extract_classic

ROOT = Path(__file__).resolve().parents[1]
GOLD_TYPES = {"md5", "sha1", "sha256", "ip-dst", "url", "domain"}


def test_defanged_ip_and_url_are_refanged():
    got = extract_classic("beacon to 1[.]2[.]3[.]4 and hxxp://evil[.]example/x")
    assert ("ip-dst", "1.2.3.4") in got
    assert ("url", "http://evil.example/x") in got
    assert ("domain", "evil.example") in got


def test_hashes_classified_by_length():
    md5 = "d41d8cd98f00b204e9800998ecf8427e"
    sha1 = "da39a3ee5e6b4b0d3255bfef95601890afd80709"
    sha256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    sha512 = "cf83e1357eefb8bdf1542850d66d8007d620e4050b5715dc83f4a921d36ce9ce" * 2
    got = extract_classic(f"{md5} {sha1} {sha256} {sha512}")
    assert {("md5", md5), ("sha1", sha1), ("sha256", sha256), ("sha512", sha512)} <= set(got)


def test_ip_url_yields_no_domain():
    got = extract_classic("see http://10.0.0.1/payload.bin")
    assert ("url", "http://10.0.0.1/payload.bin") in got
    assert not [v for t, v in got if t == "domain"]


def test_email_plain_and_defanged():
    assert ("email", "bad@evil.example") in extract_classic("mail bad@evil.example now")
    assert ("email", "bad@evil.example") in extract_classic("mail bad[@]evil[.]example now")


def test_result_sorted_and_unique():
    got = extract_classic("1.2.3.4 then 1.2.3.4 and http://a.example/ http://a.example/")
    assert got == sorted(set(got))


def test_gate_gold_iocs_are_a_subset():
    gold = json.loads((ROOT / "fixtures/gold/orkl-sample.iocs.json").read_text("utf-8"))
    text = (ROOT / "tests/fixtures/orkl-sample.txt").read_text("utf-8")
    values = {v.lower() for _, v in extract_classic(text)}
    missing = [(t, v) for t, v in gold["indicators"] if t in GOLD_TYPES and v.lower() not in values]
    assert not missing


def test_request_path_never_imports_classic():
    for name in ("expansion/generic_ai.py", "genai/extract.py"):
        src = (ROOT / name).read_text("utf-8")
        for needle in ("iocextract", "genai.classic", "from genai import classic"):
            assert needle not in src, f"{name} must not reference {needle}"


def test_times_are_not_ipv6():
    pairs = extract_classic("seen at 23:00:15 and 21:37:23 from 2001:db8::1")
    assert pairs == [("ip-dst", "2001:db8::1")]


def test_dot_words_and_markdown_escapes_are_refanged():
    got = extract_classic("see hxxp://evil[dot]example/x and https://pastebin\\.com/raw/q81X")
    assert ("domain", "evil.example") in got
    assert ("url", "https://pastebin.com/raw/q81X") in got
