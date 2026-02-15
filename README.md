# Is Market Bluffing

미국 상장 종목(ADR 포함)에 대해 최근 n개월 내 급락 후 회복 빈도를 계산하는 웹 앱입니다.

## Stack

- Backend: FastAPI + pandas + SQLAlchemy + yfinance
- Frontend: Next.js
- Storage: SQLite (익명 세션 실행값/결과 저장)

## Metric Summary

- 종목 임계 하락률: `m * max(1, beta)`
- beta: S&P 500 (`^GSPC`) 기준
- 가격 기준: 일봉 `High/Low`
- 종목 카운트: 종목당 1회
- 복귀 판정: 오늘까지
- 티커 미선택 시: 기본 유니버스 300개

## Local Run

1. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

2. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`

## Key APIs

- `POST /api/v1/analyze`
- `GET /api/v1/runs`
- `GET /api/v1/runs/{run_id}`
- `GET /api/v1/universe/default`
- `GET /api/v1/tickers/search`

익명 세션은 `x-anon-session-id` 헤더로 식별합니다.

## S&P500 Snapshot

현재 저장소에는 기본 스냅샷 파일이 포함되어 있으며, 네트워크가 되는 환경에서는 아래 스크립트로 갱신할 수 있습니다.

```bash
cd backend
source .venv/bin/activate
python3 scripts/update_sp500_snapshot.py
```

## Deploy

- Vercel 배포 가이드: `DEPLOY_VERCEL.md`
- Render 배포 가이드(기존): `DEPLOY.md`
