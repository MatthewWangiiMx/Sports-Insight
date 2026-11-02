# Sports Insight

NBA stats site + win-probability ML model. React (Vite) frontend, FastAPI backend,
scikit-learn training pipeline, Supabase Postgres for the data.

## Project layout

- `frontend/` — Vite + React + TypeScript UI
- `backend/` — FastAPI app serving stats and predictions
- `ml/` — data ingestion, feature engineering, model training (shared modules are imported by the backend)
- `ml/models/winprob_v3.pkl` — the model the API serves (committed; scikit-learn is pinned to the version that trained it)
- `tests/` — pytest suite, run against a small generated league (`tests/synthetic.py`)
- `data/raw/`, `data/processed/` — local parquet copies (gitignored)

## How data flows

```
stats.nba.com --(GitHub Actions, daily, via residential proxy)--> Supabase Postgres
Supabase --(loaded at startup, re-checked every 5 min)--> FastAPI backend --> React frontend
```

stats.nba.com blocks cloud servers, so the daily job (`.github/workflows/daily-update.yml`)
routes through the proxy in the `NBA_PROXY` secret. Without `DATABASE_URL` everything falls
back to the local parquet files in `data/raw/nba/`.

## Local development

`backend/.env` (gitignored) holds local settings:

```
DATABASE_URL=postgresql://...   # Supabase session pooler string
NBA_PROXY=http://user:pass@host:port   # optional; only needed off a home network
```

Backend:

```
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --reload
```

Runs at http://127.0.0.1:8000 (`GET /health` shows the data source and latest game).

ML pipeline (pull data, build features, train):

```
cd ml
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m ingest.update          # current season -> parquet + Supabase
.venv\Scripts\python prepare_features.py
.venv\Scripts\python train.py
```

Frontend:

```
cd frontend
npm install
npm run dev
```

Runs at http://localhost:5173. Set `VITE_API_BASE_URL` to point it at another API.

## Tests

```
pip install -r requirements-dev.txt
pytest                      # backend + ML, from the repo root
cd frontend && npm test     # frontend (npm run test:watch while developing)
```

CI (`.github/workflows/ci.yml`) runs both on every push and pull request.

## Deployment

- **Backend → Render**, from `render.yaml` (Blueprint). Set `DATABASE_URL` and
  `CORS_ORIGINS` (the frontend's URL) when prompted. Deploys only after CI passes.
- **Frontend → Vercel**, root directory `frontend`, with `VITE_API_BASE_URL` set to the
  Render URL. It's read at build time, so redeploy after changing it.
- **Daily data → GitHub Actions**, with repository secrets `DATABASE_URL` and `NBA_PROXY`.

Upgrading scikit-learn means retraining the model and updating the pin in both
`backend/requirements.txt` and `ml/requirements.txt` (the tests fail if they drift).
