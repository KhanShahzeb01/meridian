# Meridian Finance

AI financial terminal — like [Plexus](https://github.com/KhanShahzeb01/plexus), **100% static on GitHub Pages**. Your OpenRouter key stays in the browser. Market data loads from Yahoo Finance in the browser. No Render, no backend required to launch.

**Live:** [https://KhanShahzeb01.github.io/meridian/](https://KhanShahzeb01.github.io/meridian/)

## Features

- **Live market pulse** — S&P 500, NASDAQ, Dow, Gold, Crude, VIX + Yahoo headlines (browser → Yahoo)
- **36 personas** — Buffett, Munger, Simons, Dalio, and more
- **Terminal** — `/quote`, `/ask`, `/personas`, OpenRouter AI via Settings
- **Browser-only API key** — localStorage only, never saved on a server

Optional **local backend** (`backend/`) unlocks full rallies slash commands (`/memo`, `/research`, `/dcf`, etc.) for development.

---

## Deploy (GitHub Pages — same idea as Plexus)

```bash
git push origin main
```

1. **Settings → Pages → Source:** **GitHub Actions**
2. Optional variable **`MERIDIAN_BASE_PATH`** = `/meridian` (default in workflow)
3. Push to `main` — site builds and deploys automatically

No `MERIDIAN_API_URL`, no Render, no secrets.

---

## Local development (full rallies backend)

### Backend (optional — all slash commands)

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
# For full API: uncomment NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 in .env.local
npm run dev
```

Open [http://127.0.0.1:3000](http://127.0.0.1:3000)

### API key (required for AI)

1. [openrouter.ai/keys](https://openrouter.ai/keys)
2. Terminal → **Settings** (⚙) or `/key sk-or-v1-…`
3. Stored **only in your browser**

---

## Commands (GitHub Pages)

| Command | Description |
|---------|-------------|
| `/quote AAPL` | Yahoo price in browser |
| `/ask buffett …` | Persona via OpenRouter |
| `/personas` | List 36 investors |
| `/help` | Command summary |
| `/clear` | Clear terminal |

Full rallies commands need the optional local backend — see above.

---

## Tech stack

- **Frontend:** Next.js 16 static export → GitHub Pages
- **AI:** OpenRouter (direct from browser, like Plexus)
- **Market data:** Yahoo Finance APIs (browser)
- **Optional backend:** FastAPI + vendored rallies (`backend/`)
