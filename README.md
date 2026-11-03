# Wikipedia Transparency Layer — Phase 1

Who wrote the Wikipedia text you are reading, and did Wikipedia later sanction any of those
editors? Give the tool an article title and it writes:

- `out/<Article>/<revid>.json`: the claim-level record (authorship per editor and per sentence,
  accountability, and every revision ID behind each number)
- `out/<Article>/<revid>.html`: a plain one-page report

Phase 1 covers spec families **A (authorship)** and **B (accountability)**. It makes no AI calls
and never edits Wikipedia. See `CLAUDE.md` for the brief and `docs/spec.md` for the full design.

## Quick start

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
export WTL_CONTACT="you@example.org"        # required (or put it in a git-ignored .wtl-contact file)
.venv/bin/python -m wtl analyze "Gaza war"   # latest revision
.venv/bin/python -m wtl analyze "Gaza war" --revid 1234567890
.venv/bin/python -m wtl testset              # all articles in data/articles.csv + out/summary.html
.venv/bin/python -m pytest                   # unit tests, offline
```

| Command | What it does |
|---|---|
| `analyze TITLE [--revid N] [--area A-I]` | One article. Redirects are followed. Topic area comes from `data/articles.csv` unless given. |
| `testset [--refresh]` | Every article in `data/articles.csv`. Revisions are pinned in `out/testset.json`; `--refresh` moves them to the latest. |
| `render` | Rebuild every HTML page and `out/summary.html` from the stored JSON. |
| `verify-sanctions` | Open every row's link in `data/sanctions.csv` and confirm it; writes `docs/sanctions-verification.md`. |
| `check` | Totals, anonymity and byte-for-byte reproducibility for the test set; writes `out/checks.json`. |
| `spotcheck [--n 20] [--seed 1]` | Random sentences checked against the diff that added them; writes `docs/spotcheck.md`. |
| `site` | Build the public website in `site/` (home, article pages, comparison, method, objective, about) from the stored JSON. Built and published nightly by `.github/workflows/nightly.yml`, which also analyses the next batch. |

## Method

**Words.** WikiWho (GESIS, hosted on Wikimedia Cloud) splits each revision into tokens and
records the revision that first added each one. Tokens come back lower-cased without whitespace,
so `wtl/text/align.py` maps them back onto the revision's wikitext. A *word* is a token that
contains a letter or digit and lies in readable prose. Each word has exactly one author, the
editor of its origin revision, so shares always add up to 100%. WikiWho credits a word to its
first author even if it was later removed and restored.

**Readable prose** (`wtl/text/wikitext.py`): running text, the visible part of links, bold and
italic text, block quotes, and the text argument of `{{nowrap}}`, `{{lang}}` and quote templates.
Not counted: other templates (infoboxes, citations, navboxes), references, tables, files and their
captions, categories, comments, headings, and appendix sections (References, Notes, See also,
Further reading, External links and similar).

**Lead** = everything before the first heading.

**Sentences** (`wtl/text/sentences.py`) are rule-based: a sentence ends at `.`, `!` or `?`
followed by a space and a non-lower-case character, unless the word before the full stop is a known
abbreviation or an initial; line breaks and headings always end a sentence. IDs are `lead-N` and
`secK-N` (K = section number). For each sentence the record lists its authors by word count, the
revisions its words came from, and `added_revision` (the revision that contributed most words).

**Editors** are identified by user ID (or by name for IP and temporary accounts) through the
page history, and shown only as labels. `Editor 1` has the most words; ties go to the editor whose
surviving text is older. Labels are stable for a given revision.

**Concentration**: share of the top 1, 3, 5 and 10 editors; the Herfindahl index (sum of squared
shares); and how many editors wrote 50% and 80%. The same is computed for the lead.

**Survival** uses WikiWho's full token history (`all_content`): every word ever added, with the
revisions that removed and restored it. A word *survives* a horizon (48 hours, 30 days, 365 days)
if it is present at that moment after it was added. Words added less than the horizon before the
analysed revision are left out of that horizon, and events after the analysed revision are ignored.
Each editor's rate is shown next to the article average (`vs_article` = ratio). The article average
includes vandalism, which is removed quickly, so most regular editors sit above it. Survival counts
every word token, including words inside templates, because removed tokens have no position in
the current text.

**Sanctions** come from two sources, and one rule decides which apply to an article:
*a topic ban counts on articles in the same topic area; a site ban or a sockpuppetry finding counts
everywhere.* The code has no notion of sides.

1. `data/sanctions.csv`, a hand-curated seed list. Each row has the account name as written in
   the decision, type, area, duration, date, authority, a permalink to a fixed revision of the
   page that records it, and the exact quote. `verify-sanctions` checks every row against its link.
   Renamed accounts are followed through Wikipedia's rename log. Covered so far:
   - Arab–Israeli conflict (A-I): ArbCom decisions (January 2024 canvassing motion, December 2024
     and April 2025 off-wiki misconduct notices, the January 2025 PIA5 case, the January 2026
     review), plus user topic bans in the arbitration enforcement log for 2023–2026.
   - Controls: Eastern Europe (EE) and South Asia / India–Pakistan (SA) user topic bans from the
     same logs, 2023–2026.
   - Inclusion rule, the same for every area: a row needs a topic ban covering the whole topic
     area or the article's whole conflict. Page bans, narrower topic bans, warnings, struck
     entries, sanctions overturned on appeal, and blocks for violating an existing ban are left
     out. `scripts/sanction_candidates.py` lists the candidates; `scripts/build_seed_2026-11-03.py`
     records which were chosen.
2. Wikipedia's block log, checked for every registered account with text in the article: an
   **indefinite, sitewide** block whose logged reason cites sockpuppetry, multiple accounts, block
   evasion or long-term abuse counts as a sockpuppetry finding. One citing a site, community or
   ArbCom ban counts as a site ban. Partial and time-limited blocks are not counted. The block
   status is snapshotted once per analysed revision.

**Before or after**: each word by a sanctioned editor is compared with the date of that editor's
earliest applicable sanction. For a sentence, `added_before_sanction` is `true` if all its
sanctioned words predate the sanction and `false` if all postdate it. It is `null` when the
sentence has no sanctioned words, or when they are mixed (see `sanctioned_words_before` and
`sanctioned_words_after`).

## Reproducibility

- Raw responses are cached in `cache/` under the revision ID (revision text, WikiWho tokens, diffs)
  and are never refetched. Page history is extended only with newer revisions. WikiWho's token
  history is reused for any revision it covers.
- `computed` is the date of the block-status snapshot, the only time-dependent input. Rerunning
  the same revision reuses the snapshot, so the JSON is byte-identical. `inputs` records the
  sanctions file's SHA-256 and the exact URLs used.

## Anonymity

Editors appear only as `Editor N` with facts about their text. The JSON has no username field.
The HTML shows no usernames in visible text; names can appear only inside evidence links (diffs,
decisions) that Wikipedia already publishes. `check` scans every report's visible text for every
account name in the page history and the sanctions list. The tool never links accounts to people
and uses no off-wiki data about editors.

## Limits (Phase 1)

- The seed list is not complete: it starts in 2023 and covers three topic areas. A 0% sanction
  share means no matching sanction was found, not that none exists. Sanctions from before 2023, the
  editing-restrictions list, and the sockpuppet-investigation archives are not yet parsed (block
  reasons cover most confirmed socks).
- Sanction figures are comparable across articles only where the seed list covers each area to a
  similar depth; `accountability.sanctions_list` reports that coverage.
- Bans lifted after 2026-11-03, or lifted without a note in the logs used, are not tracked.
- Templates that print prose (for example `{{convert}}`) are not counted as text.
