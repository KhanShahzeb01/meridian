#!/usr/bin/env bash
# Build Next.js static export and publish to repo root (Plexus-style GitHub Pages).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/frontend"

export NEXT_PUBLIC_BASE_PATH=/meridian
npm run build

# Remove old published assets at repo root (keep backend/, frontend/, docs/)
cd "$ROOT"
rm -rf docs
for item in _next terminal _not-found 404 404.html index.html index.txt favicon.ico \
  file.svg globe.svg next.svg vercel.svg window.svg __next.*.txt; do
  rm -rf "$item" 2>/dev/null || true
done

cp -r frontend/out/. "$ROOT/"
touch "$ROOT/.nojekyll"

# Refresh gh-pages branch (static-only, for GitHub Pages)
if git -C "$ROOT" rev-parse --git-dir >/dev/null 2>&1; then
  git -C "$ROOT" push origin main 2>/dev/null || true
  STATIC_TMP=$(mktemp -d)
  cp -r "$ROOT"/index.html "$ROOT"/404.html "$ROOT"/favicon.ico "$ROOT"/.nojekyll "$STATIC_TMP/" 2>/dev/null || true
  cp -r "$ROOT"/_next "$ROOT"/terminal "$ROOT"/404 "$ROOT"/_not-found "$STATIC_TMP/" 2>/dev/null || true
  cp "$ROOT"/*.svg "$STATIC_TMP/" 2>/dev/null || true
  cd "$STATIC_TMP"
  git init -q
  git -c user.name="KhanShahzeb01" -c user.email="99250473+KhanShahzeb01@users.noreply.github.com" add -A
  git -c user.name="KhanShahzeb01" -c user.email="99250473+KhanShahzeb01@users.noreply.github.com" commit -q -m "Update GitHub Pages site"
  git remote add origin git@github.com:KhanShahzeb01/meridian.git 2>/dev/null || git remote set-url origin git@github.com:KhanShahzeb01/meridian.git
  git push -f origin HEAD:gh-pages
  rm -rf "$STATIC_TMP"
fi

echo "Done. Enable Pages: Settings → Deploy from branch → gh-pages / (root)"
