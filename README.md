# Meridian Finance

Like [Plexus](https://github.com/KhanShahzeb01/plexus) — static site on GitHub Pages, OpenRouter key in browser only.

**Live:** https://KhanShahzeb01.github.io/meridian/

---

## ⚠️ If you see “404 — There isn't a GitHub Pages site here”

GitHub Pages is **not enabled** or pointed at the wrong source. Do this **once**:

1. Open **https://github.com/KhanShahzeb01/meridian/settings/pages**
2. Under **Build and deployment → Source**, choose **Deploy from a branch** (NOT “GitHub Actions”)
3. **Branch:** `gh-pages` → folder **`/ (root)`** → **Save**
4. Wait 1–2 minutes, refresh https://KhanShahzeb01.github.io/meridian/

(Plexus uses the same flow with branch `main` / root — this repo uses branch `gh-pages` because source code also lives here.)

---

## Update the live site

```bash
cd frontend && npm run build:pages
cd .. && git add -A && git commit -m "Update site" && git push
# Also refresh gh-pages (re-run publish script pushes are on main; for gh-pages run the script in README backend section)
```

From `frontend/`:

```bash
npm run build:pages
```

Then commit root `index.html`, `_next/`, `terminal/`, etc. on `main`, and push `gh-pages` again (see `scripts/publish-pages.sh`).

---

## Local dev

```bash
cd frontend && npm install && npm run dev
```

Open http://127.0.0.1:3000 — optional backend in `backend/` for full rallies commands.

## API key

Terminal → **Settings** (⚙) → paste OpenRouter key → stored in browser only.
