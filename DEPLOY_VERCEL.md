# Vercel Deployment Guide

이 프로젝트는 `프론트엔드(Next.js)`와 `백엔드(FastAPI)`를 각각 Vercel 프로젝트로 배포하는 것을 권장합니다.

## 0) 사전 준비

1. GitHub 리포 확인
- `https://github.com/poi1649/is_market_bluffing`

2. 외부 Postgres 준비 (권장: Neon/Supabase)
- Vercel 서버리스 환경에서는 로컬 SQLite 영구 저장이 불가능합니다.
- `DATABASE_URL`은 Postgres 연결 문자열로 설정하세요.

## 1) 백엔드 배포 (Vercel Project A)

1. Vercel 대시보드 > `Add New...` > `Project`
2. GitHub repo `poi1649/is_market_bluffing` 선택
3. **Root Directory**를 `backend`로 설정
4. Deploy

백엔드 루트에는 아래 파일이 이미 준비되어 있습니다.
- `backend/api/index.py`
- `backend/vercel.json`

### Backend 환경변수

Vercel > Backend Project > `Settings` > `Environment Variables`

필수:
- `APP_ENV=production`
- `DATABASE_URL=postgresql+psycopg2://...`
- `PRICE_CACHE_DIR=/tmp/prices`
- `META_CACHE_DIR=/tmp/meta`
- `DEFAULT_UNIVERSE_SIZE=300`
- `STRICT_ORIGIN_CHECK=true`

프론트 URL 확인 후 설정:
- `FRONTEND_ORIGIN=https://<your-frontend-domain>`
- `FRONTEND_ORIGINS_CSV=https://<your-frontend-domain>`

저장 후 `Redeploy`.

## 2) 프론트 배포 (Vercel Project B)

1. Vercel 대시보드 > `Add New...` > `Project`
2. 같은 GitHub repo 선택
3. **Root Directory**를 `frontend`로 설정
4. 아래 환경변수 입력
- `NEXT_PUBLIC_API_BASE_URL=https://<your-backend-domain>`
5. Deploy

## 3) CORS 최종 정리

프론트 배포 URL이 확정되면,
- Backend 프로젝트의 `FRONTEND_ORIGIN`, `FRONTEND_ORIGINS_CSV`를 정확한 프론트 URL로 업데이트
- Backend `Redeploy`

## 4) 동작 확인

1. Backend Health
- `https://<backend-domain>/healthz`
- 기대값: `{\"status\": \"ok\"}`

2. Frontend
- `https://<frontend-domain>` 접속
- 티커 입력 후 분석 실행

## 5) 주의사항

- Vercel 서버리스는 파일시스템이 영구 저장되지 않습니다.
  - DB는 반드시 외부 Postgres 사용 권장
  - 가격/메타 캐시는 `/tmp` 임시 캐시만 사용
- 300개 기본 유니버스 분석은 응답 시간이 길어질 수 있습니다.
