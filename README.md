# Meridian Finance

AI financial terminal — like [Plexus](https://github.com/KhanShahzeb01/plexus), **100% static on GitHub Pages**. Your OpenRouter key stays in the browser.

**Live:** [https://KhanShahzeb01.github.io/meridian/](https://KhanShahzeb01.github.io/meridian/)

## Deploy (same as Plexus)

```bash
# 1. Build static site into docs/
cd frontend && npm run build:pages

# 2. Commit and push
cd .. && git add docs/ && git commit -m "Update GitHub Pages site" && git push

# 3. Enable GitHub Pages (one time):
#    Settings → Pages → Deploy from branch → main → /docs → Save
```

No GitHub Actions. No Render. No backend.

## Features

- **Live market pulse** — indices + Yahoo headlines (browser → Yahoo)
- **36 personas** — Buffett, Munger, Simons, Dalio, and more
- **Terminal** — `/quote`, `/ask`, OpenRouter via Settings (browser-only key)

## Local development

```bash
cd frontend && npm install && npm run dev
```

Optional full rallies backend: see `backend/README` in repo — run `uvicorn main:app --port 8000` and set `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000` in `frontend/.env.local`.

## API key

1. [openrouter.ai/keys](https://openrouter.ai/keys)
2. Terminal → **Settings** (⚙)
3. Stored only in your browser (localStorage)
