# Deployment (Render)

이 저장소는 Render Blueprint(`render.yaml`)로 백엔드/프론트를 함께 배포할 수 있습니다.

## 1) 저장소 푸시

```bash
git add .
git commit -m "Add deployment config"
git push origin <branch>
```

## 2) Render에서 Blueprint 배포

1. Render Dashboard > New > Blueprint
2. 이 저장소 연결
3. `render.yaml` 확인 후 Deploy

## 3) HTTPS 도메인

- Render 기본 도메인은 자동 HTTPS(SSL) 제공
- 예시:
  - Backend: `https://is-market-bluffing-backend.onrender.com`
  - Frontend: `https://is-market-bluffing-frontend.onrender.com`

## 4) 반드시 확인할 환경변수

- Backend
  - `FRONTEND_ORIGIN`
  - `FRONTEND_ORIGINS_CSV`
- Frontend
  - `NEXT_PUBLIC_API_BASE_URL`

도메인 이름이 실제 배포 시 달라지면 위 값을 Render 콘솔에서 맞춰주세요.

## 5) 배포 후 점검

- Backend health: `GET /healthz`
- Frontend에서 분석 실행
- 브라우저 콘솔 CORS 에러 없는지 확인

## 참고

- SQLite를 `/var/data` 디스크에 저장하도록 구성되어 재배포 시 데이터가 유지됩니다.
- 추후 운영 안정성을 위해 PostgreSQL로 전환을 권장합니다.
