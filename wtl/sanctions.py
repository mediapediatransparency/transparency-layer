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

    def applies_to(self, article_area: str) -> bool:
        return self.type != "topic_ban" or self.area == article_area

    def public(self) -> dict:
        """What the output may contain: no username field (it can appear inside the link)."""
        return {"type": self.type, "area": self.area, "duration": self.duration,
                "date": self.date, "authority": self.authority, "source": self.source,
                "evidence": self.url}


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
            rows.append(Sanction(r["username"].strip(), r["sanction_type"], r["area"],
                                 r["duration"], r["date"], r["authority"],
                                 r["decision_url"].strip(), "seed_list"))
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
