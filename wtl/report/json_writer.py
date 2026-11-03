"""Deterministic JSON output: same record in, byte-identical file out."""

import json
import re
from pathlib import Path

from ..config import OUT_DIR


def slug(title: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "-", title.replace(" ", "_"))


def dumps(record: dict) -> str:
    return json.dumps(record, ensure_ascii=False, indent=1, allow_nan=False) + "\n"


def write(record: dict, out_dir: Path = OUT_DIR) -> Path:
    d = out_dir / slug(record["article"])
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{record['revision']}.json"
    p.write_text(dumps(record), encoding="utf-8")
    return p
