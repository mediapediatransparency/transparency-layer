#!/bin/sh
# Publish the website to GitHub Pages from this computer.
#
# Builds a public copy of the site in out/site-public/ whose "full data" links point to the
# article records in this repository (out/<article>/<revision>.json, at the commit being
# published) instead of copying them beside the pages, which keeps the site under GitHub Pages'
# 1 GB limit. Then pushes that folder as the only commit of the gh-pages branch (history is not
# kept there, so the repository does not grow with every publish). The push goes through this
# repository's own git settings, so it uses the project's GitHub account.
#
# Run from anywhere:  scripts/publish_pages.sh
set -eu
cd "$(dirname "$0")/.."

if ! git diff --quiet HEAD -- out data wtl; then
  echo "Commit the changes in out/, data/ and wtl/ first (the public pages link to the committed records)." >&2
  exit 1
fi
git fetch -q origin main
if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
  echo "Push main first: the pages link to records at the published commit." >&2
  exit 1
fi

SHA=$(git rev-parse HEAD)
REMOTE=$(git remote get-url origin)
REPO_PATH=$(echo "$REMOTE" | sed -E 's#^https://github.com/##; s#\.git$##')
export WTL_DATA_BASE="https://raw.githubusercontent.com/$REPO_PATH/$SHA/out"

.venv/bin/python -m wtl site --elsewhere-sample 5 --out out/site-public
touch out/site-public/.nojekyll      # serve files as they are (no Jekyll processing)
du -sh out/site-public

# Commit the folder from this repository (so the push uses this repository's GitHub account and
# settings), as a commit with no parent, and make it the whole of the gh-pages branch.
TMP_INDEX=$(mktemp)
rm -f "$TMP_INDEX"
GIT_INDEX_FILE="$TMP_INDEX" git --work-tree=out/site-public add -A
TREE=$(GIT_INDEX_FILE="$TMP_INDEX" git write-tree)
rm -f "$TMP_INDEX"
COMMIT=$(git commit-tree "$TREE" -m "Publish site from $SHA")
git push -f origin "$COMMIT:refs/heads/gh-pages"
echo "Published from $SHA."
