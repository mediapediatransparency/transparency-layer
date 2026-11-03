"""List candidate user sanctions from fixed revisions of the arbitration enforcement logs.

This does NOT write data/sanctions.csv. It prints candidates (username, date, quote, permalink)
for a human to read and copy into the seed list. Accuracy over coverage: anything ambiguous is
left out of the CSV.

Usage: .venv/bin/python scripts/sanction_candidates.py > /tmp/candidates.tsv
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from wtl.fetch.mediawiki import page_wikitext  # noqa: E402

# (area, page revision id, regex for the heading that opens the user-sanctions section)
SOURCES = [
    ("A-I", 1363549031, r"^===\[\[Wikipedia:Requests for arbitration/Palestine-Israel articles"),
    ("A-I", 1377716639, r"^====User sanctions \(CT/A-I\)===="),
    ("A-I", 1380654105, r"^====User sanctions \(CT/A-I\)===="),
    ("A-I", 1379926042, r"^==== \[\[WP:ARBPIA5\|"),
    ("A-I", 1383113230, r"^===\[\[WP:CT/A-I\|"),
    ("A-I", 1383113230, r"^==== \[\[WP:ARBPIA5\|"),
    ("EE", 1363549031, r"^====Individual sanctions \(EE\)===="),
    ("EE", 1338962809, r"^====User sanctions \(CT/EE\)===="),
    ("EE", 1379926042, r"^====User sanctions \(CT/EE\)===="),
    ("EE", 1383113230, r"^====User sanctions \(CT/EE\)===="),
    ("SA", 1363549031, r"^====Individual sanctions \(IPA\)===="),
    ("SA", 1338962809, r"^====User sanctions \(CT/IPA\)===="),
    ("SA", 1379926042, r"^====User sanctions \(CT/IPA\)===="),
    ("SA", 1379926042, r"^====User sanctions \(CT/SA\)===="),
    ("SA", 1383113230, r"^===\[\[WP:CT/SA\|"),
]
USER = re.compile(r"\{\{\s*(?:user|userlinks|noping2?|no ping|np2?|u|checkuser|user2|user5)\s*\|"
                  r"\s*(?:1=)?([^|}]+?)\s*[|}]", re.I)
SIG = re.compile(r"(\d{1,2}):(\d{2}), (\d{1,2}) (\w+) (\d{4}) \(UTC\)")
MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June",
                                      "July", "August", "September", "October", "November",
                                      "December"], start=1)}


def section(w: str, pat: str) -> str:
    m = re.search(pat, w, re.M)
    if not m:
        return ""
    level = len(re.match(r"=+", w[m.start():]).group(0))
    rest = w[m.end():]
    n = re.search(r"^={2,%d}[^=]" % level, rest, re.M)
    return rest[:n.start()] if n else rest


def main():
    print("\t".join(["area", "revid", "title", "username", "date", "line"]))
    for area, revid, pat in SOURCES:
        page = page_wikitext(revid)
        body = section(page["wikitext"], pat)
        if not body:
            print(f"# no section {pat!r} in {revid}", file=sys.stderr)
        for line in body.split("\n"):
            if not re.search(r"topic[- ]?ban|site[- ]?ban|\bbanned\b|sock", line, re.I):
                continue
            users = USER.findall(line)
            sigs = SIG.findall(line)
            date = ""
            if sigs:
                h, mi, d, mon, y = sigs[-1]
                date = f"{y}-{MONTHS.get(mon, 0):02d}-{int(d):02d}"
            print("\t".join([area, str(revid), page["title"], ";".join(users), date,
                             line.replace("\t", " ")]))


if __name__ == "__main__":
    main()
