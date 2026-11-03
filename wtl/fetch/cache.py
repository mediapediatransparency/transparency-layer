"""Gzip JSON cache on disk. Raw API responses are keyed by revision ID wherever possible."""

import gzip
import json
from pathlib import Path

from ..config import CACHE_DIR


def path(*parts: str) -> Path:
    p = CACHE_DIR.joinpath(*parts)
    if not p.name.endswith(".json.gz"):
        p = p.with_name(p.name + ".json.gz")
    return p


def load(p: Path):
    if not p.exists():
        return None
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return json.load(f)


def save(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    # mtime=0 keeps the gzip bytes identical for identical content.
    with open(tmp, "wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as f:
            f.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    tmp.replace(p)
