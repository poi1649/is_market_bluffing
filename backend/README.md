# Backend (FastAPI)

## Run

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

## Notes

- Anonymous session id is passed via `x-anon-session-id` header.
- If no tickers are provided, `/api/v1/universe/default` is used.
- Default universe size is 300 tickers (`DEFAULT_UNIVERSE_SIZE`).
- S&P 500 default universe uses:
  1. Same-day cached Wikipedia snapshot if available.
  2. Local snapshot file (`app/data/sp500_snapshot_feb2026.csv`) fallback.
  3. Local seed file (`app/data/default_universe_300.csv`) and built-in fallback tickers as last resort.

## Update S&P500 Snapshot

```bash
cd backend
source .venv/bin/activate
python3 scripts/update_sp500_snapshot.py
```
