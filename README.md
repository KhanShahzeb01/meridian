# Meridian Finance

AI financial terminal — live market data, 36 investor personas, and rallies-powered slash commands. Landing page + web terminal.

## Features

- **Live market pulse** — S&P 500, NASDAQ, Dow, Gold, Crude Oil, VIX + paginated Yahoo headlines
- **36 personas** — Buffett, Munger, Simons, Dalio, and more
- **Fast data commands** — `/quote`, `/news`, `/financials`, `/vix`, `/macro` (sub-second)
- **Browser-only API key** — like [Plexus](https://github.com/KhanShahzeb01/plexus); your OpenRouter key stays in localStorage, never saved on the server

## Architecture

| Layer | Host | Notes |
|-------|------|--------|
| **Frontend** | GitHub Pages | Static Next.js export (`frontend/out`) |
| **Backend** | Render / Railway / local | FastAPI — market data + AI routing |

GitHub Pages serves HTML/JS only. The API must run elsewhere and be set via `NEXT_PUBLIC_API_URL` at build time.

---

## Local development

### 1. Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --host 127.0.0.1 --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) · Terminal: [http://localhost:3000/terminal](http://localhost:3000/terminal)

### 3. API key (required for AI)

1. Get a key from [openrouter.ai/keys](https://openrouter.ai/keys)
2. In the terminal, click **Settings** (⚙) or run `/key sk-or-v1-…`
3. Key is stored **only in your browser** — not on the server

---

## Deploy to GitHub Pages (frontend)

```bash
git init
git add .
git commit -m "Meridian Finance initial release"
git remote add origin https://github.com/YOUR_USERNAME/meridian-finance.git
git branch -M main
git push -u origin main
```

1. **Repository → Settings → Pages → Source:** GitHub Actions  
2. **Repository → Settings → Secrets and variables → Actions → Variables:**
   - `MERIDIAN_API_URL` — e.g. `https://meridian-api.onrender.com`
   - `MERIDIAN_BASE_PATH` — e.g. `/meridian-finance` (repo name; omit for `username.github.io` root site)
3. Push to `main` — workflow `.github/workflows/deploy-pages.yml` builds and deploys

Site URL: `https://YOUR_USERNAME.github.io/meridian-finance/`

---

## Deploy backend (Render example)

1. New **Web Service** → connect repo, root `backend`
2. Build: `pip install -r requirements.txt`
3. Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Env: `CORS_ORIGINS=https://YOUR_USERNAME.github.io`
5. Copy the service URL into GitHub variable `MERIDIAN_API_URL`

No `OPENROUTER_API_KEY` on the server in production — users supply keys in the browser.

---

## Commands

Type `/help` in the terminal. Highlights:

| Category | Commands |
|----------|----------|
| Data | `/quote`, `/financials`, `/news`, `/sec`, `/vix`, `/macro` |
| Personas | `/personas`, `/ask`, `/debate`, `/consensus` |
| Research | `/memo`, `/research`, `/dcf`, `/screen` |
| Portfolio | `/watchlist`, `/portfolio` |
| System | `/help`, `/key`, `/clear` |

---

## Tech stack

- **Frontend:** Next.js 16, TypeScript, Tailwind CSS
- **Backend:** FastAPI, yfinance, Yahoo Finance
- **AI:** OpenRouter (user-provided key)
- **Engine:** Vendored rallies in `backend/vendor/rallies/`
