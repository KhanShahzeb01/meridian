# Meridian Finance

Like [Plexus](https://github.com/KhanShahzeb01/plexus) — static site on GitHub Pages, OpenRouter key in browser only.

**Live:** https://KhanShahzeb01.github.io/meridian/

---

## GitHub Pages

**Settings → Pages → Deploy from branch → `main` → `/docs`**

After changing settings or pushing a new build, wait 1–2 minutes for the site to update.

---

## Update the live site

```bash
cd frontend && npm run build:pages
cd .. && git add docs scripts/publish-pages.sh && git commit -m "Update GitHub Pages site" && git push
```

`build:pages` runs `scripts/publish-pages.sh`, which builds Next.js with `NEXT_PUBLIC_BASE_PATH=/meridian` and copies output into `docs/`.

---

## Local dev

```bash
cd frontend && npm install && npm run dev
```

Open http://127.0.0.1:3000 — optional backend in `backend/` for full rallies commands.

## API key

Terminal → **Settings** (⚙) → paste OpenRouter key → stored in browser only.
