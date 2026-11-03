"""Map WikiWho tokens back onto the revision's wikitext.

WikiWho tokens are lower-cased substrings of the wikitext, in order, with whitespace dropped.
Walking the lower-cased text with a cursor recovers each token's character span, which lets us
keep the original casing and layout and decide whether a token is readable prose.
"""

from dataclasses import dataclass


@dataclass
class Alignment:
    spans: list            # (start, end) per token, or None if the token could not be placed
    unaligned: int         # tokens not found
    skipped_chars: int     # non-whitespace characters jumped over between tokens


def align(text: str, tokens: list[str]) -> Alignment:
    low = text.lower()
    if len(low) == len(text):
        to_orig = None
    else:  # rare: a character whose lower-case form has a different length (e.g. 'İ')
        parts, to_orig = [], []
        for i, c in enumerate(text):
            lc = c.lower()
            parts.append(lc)
            to_orig.extend([i] * len(lc))
        low = "".join(parts)

    spans, unaligned, skipped = [], 0, 0
    cur = 0
    for tok in tokens:
        if not tok:
            spans.append(None)
            continue
        i = low.find(tok, cur)
        if i < 0:
            spans.append(None)
            unaligned += 1
            continue
        gap = low[cur:i]
        skipped += len(gap) - sum(1 for ch in gap if ch.isspace())
        j = i + len(tok)
        if to_orig is None:
            spans.append((i, j))
        else:
            spans.append((to_orig[i], to_orig[j - 1] + 1))
        cur = j
    return Alignment(spans, unaligned, skipped)
