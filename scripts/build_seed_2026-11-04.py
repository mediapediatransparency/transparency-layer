"""Rows added to data/sanctions.csv on 2026-11-04 (kept for provenance).

Rule agreed that day: every topic ban within an area counts, whatever its scope, and the scope is
recorded in the notes ("scope: ..."), as for the Arab-Israeli rows. Every row was chosen by
reading its candidate line (scripts/sanction_candidates.py output); this script only formats the
chosen rows and asserts that each quote appears verbatim at its permalink.

Left out on purpose: blocks for breaking an existing ban, page bans, interaction bans, page
protections, warnings, entries struck through on the log without a recorded lift, entries
without a date, and sock entries that do not name the sock account.

Usage: python scripts/build_seed_2026-11-04.py candidates.tsv
"""
import csv
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from wtl.fetch.mediawiki import page_wikitext  # noqa: E402

CAND = sys.argv[1]
rows = list(csv.reader(open(CAND, encoding="utf-8"), delimiter="\t"))[1:]

# (candidate index, username, type, duration, authority, notes)
CHOSEN = [
    # Eastern Europe
    (128, "Michael60634", "topic_ban", "until 2023-07-15", "AE", "scope: Crimea"),
    (131, "Товболатов", "topic_ban", "indefinite", "admin",
     "scope: ethnic minority groups in the former Soviet Union"),
    (134, "Elbrusoid1507", "topic_ban", "indefinite", "admin",
     "scope: minority ethnic groups in Russia and the former Soviet Union"),
    (139, "My very best wishes", "topic_ban", "indefinite", "AE",
     "scope: World War II in Eastern Europe and the history of Jews in Eastern Europe; "
     "repealed by Arbitration Committee motion on 2024-08-08 (same log)"),
    (142, "Balkanite", "topic_ban", "6 months and 500 edits", "admin", "scope: Bosniak topics"),
    (143, "Balkanite", "sockpuppet", "indefinite", "admin",
     "sub-entry under the Balkanite entry: later indefinitely blocked as a sock"),
    (144, "Crash48", "topic_ban", "until 2024-12-29", "AE", "scope: Ukrainian language"),
    (145, "Rsk6400", "topic_ban", "until 2024-12-29", "AE", "scope: Ukrainian language"),
    (146, "Pofka", "topic_ban", "indefinite", "ArbCom (AE)", "scope: Lithuania"),
    (150, "Anonimu", "topic_ban", "not stated", "AE (appeal)",
     "scope: post-2000 Russia/Ukraine relations; the ban predates 2023 and the date is when "
     "this scope was set"),
    (151, "Lemabeta", "topic_ban", "indefinite", "AE",
     "scope: history of the Caucasus and its cultural heritage"),
    (152, "Shahray", "topic_ban", "3 months", "admin", "scope: history of Ukraine and the Rus'"),
    (157, "Dr Dijon Ethem Kurti", "topic_ban", "indefinite", "admin",
     "scope: Albanian and Serbian topics"),
    (159, "Bildete", "topic_ban", "1 year", "admin", "scope: Poland and Lithuania"),
    # South Asia
    (170, "Dev0745", "topic_ban", "indefinite", "admin",
     "scope: India, Pakistan and Afghanistan; narrowed on 2025-01-11 to politics, religion and "
     "culture in India and Pakistan (same log)"),
    (188, "Videh raj", "topic_ban", "indefinite", "admin",
     "scope: caste and social groups in India and Pakistan"),
    (197, "Genuinewikiuser", "topic_ban", "indefinite", "admin (unblock condition)",
     "scope: the South Asia area"),
    (209, "GenuineArt", "topic_ban", "indefinite", "admin", "scope: Indian politics and history"),
    (216, "Bhaskar sunsari", "topic_ban", "indefinite", "AE", "scope: South Asian social groups"),
    (217, "HistorianAlferedo", "topic_ban", "indefinite", "admin",
     "scope: caste or social groups"),
    (219, "Lt.gen.zephyr", "topic_ban", "indefinite", "admin",
     "scope: military topics related to Bangladesh"),
    (221, "Rejoy2003", "topic_ban", "indefinite", "admin",
     "scope: Indian and/or Portuguese nationality designations"),
    (223, "Lucasattitude", "topic_ban", "indefinite", "AE", "scope: Dhurandhar (film)"),
    (228, "Zorawar385", "topic_ban", "indefinite", "admin", "scope: Indian military history"),
]
# lifts recorded on the log: (row index of the sanction, row index of the lift entry, date)
LIFTS = {139: (140, "2024-08-08")}

import re  # noqa: E402

# Same quote and link rules as scripts/build_seed_2026-11-03.py
SIGCUT = re.compile(r"\s*(<sub>signed|\[\[User:|\[\[user:|<span|<b>\s*\[\[|—&nbsp;|--\s*\[\[|-- \[\[|~ Jenson|"
                    r"<small class=\"autosigned\"|<!--|- \[\[User)")


def quote_of(line):
    q = line.lstrip("*:# ")
    m = SIGCUT.search(q)
    if m:
        q = q[:m.start()]
    q = q.rstrip(" .-")
    if len(q) > 240:
        q = q[:240].rsplit(" ", 1)[0]
    return q


def rendered(q):
    t = re.sub(r"\{\{\s*(?:user|userlinks|noping2?|no ping|np2?|u|checkuser|usertcb)\s*\|\s*([^|}]+)\}\}",
               r"\1", q, flags=re.I)
    t = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", t)
    t = re.sub(r"\[https?://\S+ ([^\]]*)\]", r"\1", t)
    t = re.sub(r"\{\{[^}]*\}\}|<[^>]+>|'''?|\[https?://\S+\]", "", t)
    return " ".join(t.split())


def frag(q):
    words = rendered(q).split()[:6]
    return "#:~:text=" + urllib.parse.quote(" ".join(words), safe="").replace("-", "%2D")

pages = {}


def page(revid):
    if revid not in pages:
        pages[revid] = page_wikitext(revid)
    return pages[revid]


def permalink(title, revid, q):
    return (f"https://en.wikipedia.org/w/index.php?title={urllib.parse.quote(title.replace(' ', '_'))}"
            f"&oldid={revid}{frag(q)}")


out = []
for idx, user, typ, dur, auth, notes in CHOSEN:
    area, revid, title, users, date, line = rows[idx - 1]
    parent = rows[idx - 2] if typ == "sockpuppet" and not users else None
    assert user in users.split(";") or user in line or (parent and user in parent[5]), (idx, user)
    assert date, (idx, user)
    q = quote_of(line)
    assert q in page(int(revid))["wikitext"], (idx, q)
    lifted_date = lift_url = ""
    if idx in LIFTS:
        li, lifted_date = LIFTS[idx]
        la, lrev, ltitle, _, ldate, lline = rows[li - 1]
        lq = quote_of(lline)
        assert lq in page(int(lrev))["wikitext"], (li, lq)
        lift_url = permalink(ltitle, lrev, lq)
    out.append({"username": user, "sanction_type": typ, "area": area, "duration": dur,
                "date": date, "authority": auth, "decision_url": permalink(title, revid, q),
                "source_quote": q, "notes": notes, "lifted_date": lifted_date,
                "lift_url": lift_url})

path = ROOT / "data" / "sanctions.csv"
with open(path, newline="", encoding="utf-8") as f:
    old = list(csv.DictReader(f))
have = {(r["username"], r["area"], r["date"], r["sanction_type"]) for r in old}
new = [r for r in out if (r["username"], r["area"], r["date"], r["sanction_type"]) not in have]
cols = ["username", "sanction_type", "area", "duration", "date", "authority", "decision_url",
        "source_quote", "notes", "lifted_date", "lift_url"]
with open(path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    for r in old + new:
        w.writerow({c: r.get(c, "") for c in cols})
print(f"added {len(new)} rows; {len(old) + len(new)} in all")
