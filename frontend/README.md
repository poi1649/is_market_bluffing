# Frontend (Next.js)

## Run

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

- API base URL is read from `NEXT_PUBLIC_API_BASE_URL`.
- Anonymous session id is stored in browser localStorage and sent as `x-anon-session-id`.
