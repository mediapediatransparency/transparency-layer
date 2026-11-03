"""The hand-verified sanctions seed list (data/sanctions.csv) and block-log findings.

One rule decides which sanctions apply to an article, the same for every editor:
- a topic ban applies to articles in the same topic area as the ban;
- a site ban or a sockpuppetry finding applies to every article.
"""

import csv
import hashlib
import re
from dataclasses import dataclass

from .config import SANCTIONS_CSV

TYPES = {"topic_ban", "site_ban", "sockpuppet"}
AREAS = {"A-I", "EE", "SA"}
COLUMNS = ["username", "sanction_type", "area", "duration", "date", "authority",
           "decision_url", "source_quote", "notes"]
# Optional, hand-verified: when a sanction actually ended early (lifted or overturned on appeal),
# with a link to the record of that.
OPTIONAL = ["lifted_date", "lift_url"]


@dataclass(frozen=True)
class Sanction:
    username: str
    type: str
    area: str
    duration: str
    date: str          # YYYY-MM-DD (UTC)
    authority: str
    url: str
    source: str        # "seed_list" or "block_log"
    end: str = ""      # YYYY-MM-DD when the sanction stopped applying; "" = no end known
    end_basis: str = ""  # "duration", "lifted" or "" (open-ended or not stated)
    lift_url: str = ""

    def applies_to(self, article_area: str) -> bool:
        return self.type != "topic_ban" or self.area == article_area

    def public(self) -> dict:
        """What the output may contain: no username field (it can appear inside the link)."""
        out = {"type": self.type, "area": self.area, "duration": self.duration,
               "date": self.date, "end": self.end or None, "end_basis": self.end_basis or None,
               "authority": self.authority, "source": self.source, "evidence": self.url}
        if self.lift_url:
            out["lift_evidence"] = self.lift_url
        return out


_UNITS = {"day": 1, "week": 7, "month": None, "year": None}


def end_from_duration(start: str, duration: str) -> str:
    """End date implied by a fixed duration ("90 days", "6 months", "1 year", "until 2024-05-01",
    "6 months and 500 edits" -> the earliest possible end). "" when open-ended or not stated."""
    import datetime as dt
    d = duration.strip().lower()
    m = re.search(r"until (\d{4}-\d{2}-\d{2})", d)
    if m:
        return m.group(1)
    m = re.search(r"(\d+)\s*(day|week|month|year)s?", d)
    if not m or "indefinite" in d:
        return ""
    n, unit = int(m.group(1)), m.group(2)
    t = dt.date.fromisoformat(start)
    if unit in ("day", "week"):
        return (t + dt.timedelta(days=n * _UNITS[unit])).isoformat()
    months = n * (12 if unit == "year" else 1)
    y, mo = divmod(t.month - 1 + months, 12)
    import calendar
    day = min(t.day, calendar.monthrange(t.year + y, mo + 1)[1])
    return dt.date(t.year + y, mo + 1, day).isoformat()


def load(path=SANCTIONS_CSV) -> list[Sanction]:
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = set(COLUMNS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path}: missing columns {sorted(missing)}")
        for n, r in enumerate(reader, start=2):
            if not r["decision_url"].strip():
                raise ValueError(f"{path}:{n}: no link, no row")
            if r["sanction_type"] not in TYPES:
                raise ValueError(f"{path}:{n}: unknown sanction_type {r['sanction_type']!r}")
            if r["area"] not in AREAS:
                raise ValueError(f"{path}:{n}: unknown area {r['area']!r}")
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["date"]):
                raise ValueError(f"{path}:{n}: date must be YYYY-MM-DD")
            lifted = (r.get("lifted_date") or "").strip()
            if lifted and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", lifted):
                raise ValueError(f"{path}:{n}: lifted_date must be YYYY-MM-DD")
            if lifted and not (r.get("lift_url") or "").strip():
                raise ValueError(f"{path}:{n}: lifted_date needs a lift_url")
            end = end_from_duration(r["date"], r["duration"])
            basis = "duration" if end else ""
            if lifted and (not end or lifted < end):
                end, basis = lifted, "lifted"
            rows.append(Sanction(r["username"].strip(), r["sanction_type"], r["area"],
                                 r["duration"], r["date"], r["authority"],
                                 r["decision_url"].strip(), "seed_list", end, basis,
                                 (r.get("lift_url") or "").strip()))
    return rows


def file_sha256(path=SANCTIONS_CSV) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


SOCK = re.compile(r"sock|checkuser|multiple accounts|block evasion|evading (a )?block|"
                  r"\bLTA\b|long[- ]term abuse", re.I)
BAN = re.compile(r"(site|community|arbcom|arbitration committee)[- ]?ban|\bbanned (user|editor)\b|"
                 r"\{\{\s*banned|\[\[WP:(CBAN|SBAN)\b", re.I)


def classify_block(block: dict) -> str | None:
    """'sockpuppet' or 'site_ban' for an indefinite, sitewide block whose logged reason says so;
    None otherwise. Partial blocks and time-limited blocks are not counted."""
    if block.get("partial") or block.get("expiry") not in ("infinity", "infinite", "indefinite"):
        return None
    reason = block.get("reason", "")
    if SOCK.search(reason):
        return "sockpuppet"
    if BAN.search(reason):
        return "site_ban"
    return None


def block_sanction(username: str, block: dict, kind: str) -> Sanction:
    return Sanction(username, kind, "", "indefinite", block["timestamp"][:10], "block log",
                    f"https://en.wikipedia.org/wiki/Special:BlockList?wpTarget=%23{block['id']}",
                    "block_log")
