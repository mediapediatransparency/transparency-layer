# Browser add-on (local test version)

Shows a badge of four dials on Wikipedia articles this project has analysed, and a panel with
the details when the badge is clicked:

- **Source leaning:** where the audience of the cited websites sits, from −1 (shared mostly by
  Democrats) to +1 (mostly by Republicans), from DomainDemo (Yang et al. 2025). The solid needle
  is the article's own citations; the shorter needle with a ring is the sources its writers cite
  across the analysed articles, blended by each writer's share of the text. The grey line is the
  figure for all analysed articles; zero is not a political centre. Books, journals and
  scholarly sites have no leaning rating; the panel gives their share.
- **Website quality:** the independent quality ratings of the cited websites (Lin et al., 0 to 1).
- **Academic level:** the Finnish Publication Forum level of the cited publishers and journals
  (0 to 3).
- **Top 5 editors wrote:** the share of the current text written by the five largest contributors.

Under each dial: how much of the article's citations it covers. On the last three, the grey line
marks similar articles.

A needle is drawn only when at least a quarter of the citations (or of the text) is rated.
No single editor's figure is shown anywhere.

## Privacy

All data is inside the add-on (`data.js`). It never fetches anything and never sends anything:
nobody learns which pages you read. It reads the page title and revision number from the
Wikipedia page itself.

## Install in Chrome (or Edge, Brave)

1. Build the site once (`python -m wtl site`); this writes `data.js` and `local.js` here.
2. Open `chrome://extensions`, switch on **Developer mode** (top right).
3. Choose **Load unpacked** and pick this `extension` folder.
4. Open any analysed article, for example https://en.wikipedia.org/wiki/Zionism

After a new site build, press the reload arrow on the add-on's card in `chrome://extensions`.

## Before sharing a copy

`local.js` links the panel to the copy of the site on this machine and contains a local folder
path. It is git-ignored and must be left out of any copy given to others (a shared copy would
point "Full report" at the public site address instead).
