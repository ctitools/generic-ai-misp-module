"""Classical regex IoC extractor (iocextract) — testing and benchmark baseline only.

Returns a *superset* of indicators, refanging defanged values. It is never called on the
module's request path (`expansion/generic_ai.py`, `genai/extract.py` do not import it);
`tests/test_classic_unit.py` enforces that.

CLI: python -m genai.classic <textfile> [-o out.json]
"""

import argparse
import ipaddress
import json
from importlib.metadata import version
from pathlib import Path
from urllib.parse import urlsplit

import iocextract

HASH_TYPES = {32: "md5", 40: "sha1", 64: "sha256", 128: "sha512"}


def _domain(url: str) -> str | None:
    host = urlsplit(url).hostname or ""
    try:
        ipaddress.ip_address(host)
        return None
    except ValueError:
        return host or None


def extract_classic(text: str) -> list[tuple[str, str]]:
    """Sorted, de-duplicated (misp_type, value) pairs found by iocextract with refang=True."""
    found: set[tuple[str, str]] = set()
    for ip in (*iocextract.extract_ipv4s(text, refang=True), *iocextract.extract_ipv6s(text)):
        found.add(("ip-dst", ip))
    for url in iocextract.extract_urls(text, refang=True):
        found.add(("url", url))
        if domain := _domain(url):
            found.add(("domain", domain))
    for email in iocextract.extract_emails(text):  # its regex swallows the preceding word
        found.add(("email", iocextract.refang_email(email.split()[-1])))
    for digest in iocextract.extract_hashes(text):
        if kind := HASH_TYPES.get(len(digest)):
            found.add((kind, digest))
    return sorted(found)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("textfile", type=Path)
    parser.add_argument("-o", "--output", type=Path, help="write JSON here instead of stdout")
    args = parser.parse_args()
    result = {
        "tool": f"iocextract {version('iocextract')}",
        "indicators": extract_classic(args.textfile.read_text(encoding="utf-8")),
    }
    dumped = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(dumped + "\n", encoding="utf-8")
    else:
        print(dumped)


if __name__ == "__main__":
    main()
