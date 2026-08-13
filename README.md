# Sports Insight

NBA stats site + win-probability ML model. React (Vite) frontend, FastAPI backend, scikit-learn/XGBoost training pipeline.

## Project layout

- `frontend/` — Vite + React + TypeScript UI
- `backend/` — FastAPI app serving stats and predictions
- `ml/` — data ingestion, feature engineering, model training
- `data/raw/`, `data/processed/` — datasets (gitignored, generated locally)

## Backend

```
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --reload
```

Runs at http://127.0.0.1:8000. Health check: `GET /health`.

## ML pipeline

```
cd ml
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

## Frontend

```
cd frontend
npm install
npm run dev
```

Runs at http://localhost:5173.
