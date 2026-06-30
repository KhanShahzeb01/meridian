#!/usr/bin/env bash
# Build Next.js static export into docs/ for GitHub Pages (main branch /docs).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Fetching market snapshot (Yahoo Finance, server-side)…"
python3 "$ROOT/scripts/fetch-market-snapshot.py"

cd "$ROOT/frontend"
export NEXT_PUBLIC_BASE_PATH=/meridian
unset NEXT_PUBLIC_API_URL
export NEXT_PUBLIC_API_URL=
npm run build

cd "$ROOT"
rm -rf docs
mkdir -p docs
cp -r frontend/out/. docs/
touch docs/.nojekyll

# Remove accidental static files from repo root (source lives in frontend/)
for item in _next terminal _not-found 404 404.html index.html index.txt favicon.ico \
  file.svg globe.svg next.svg vercel.svg window.svg __next.*.txt .nojekyll; do
  rm -rf "$item" 2>/dev/null || true
done

echo "Built → docs/  (GitHub Pages: main branch, /docs folder)"
