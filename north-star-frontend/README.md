# North Star — Next.js 14 Frontend

Dark, animated, and RBAC-aware UI implementing your **North Star** features.

## What you get
- App Router (Next 14), Tailwind, React Query, Jotai auth state
- Beautiful cards, gradients, animations, focus rings
- Pages: Dashboard (StarView, Smart Access), NorthStar Guide (big left, A vs B + Top Evidence right, narrative modal), IntelliStaff (batch select + Assign/Assign+Jira), IntelliSelf (Dev-only Skill Signal), Aurora (agent console + Create Project + Upload), Audit (user + time filter), Admin · Users
- Login-first with golden shooting star and motto: **Your personal NorthStar 🌠**
- Logout button (client-side JWT clear). Your API does not expose `/auth/logout`, and you **do not** need a backend route—just drop the token.

## Install & run locally (copy/paste)
```bash
# 1) Install Node.js 20+ first (https://nodejs.org)

# 2) Install deps
npm i

# 3) Set API URL
cp .env.local.example .env.local
# edit .env.local to point NEXT_PUBLIC_API_BASE to your FastAPI (e.g., http://localhost:8000)
# (optional) set NEXT_PUBLIC_INTELLISTAFF_PATH if your candidate endpoint differs from /intellistaff/candidates

# 4) Start dev server
npm run dev
# open http://localhost:3000/login
```

## Build & run
```bash
npm run build
npm start
```

## Deploy on Vercel
1. Push this folder to a new GitHub repo.
2. Import into **Vercel** → Framework: **Next.js**.
3. In Project → Settings → **Environment Variables** add:
   - `NEXT_PUBLIC_API_BASE` → e.g. `https://api.example.com`
4. Deploy.

## Tests
- Unit: `npm test`
- E2E: `npm run dev` then `npm run e2e`

## Endpoint compatibility
- Assign+Jira flow uses: `POST /assignments` (for each dev), optional `POST /agent/query` (Jira), then `POST /onboarding/generate` per dev to create their plan.
- Aurora can: `POST /agent/query` and (for Admin/PO) `POST /projects` + `POST /upload`.
- Audit time-window is done client-side (your API supports `actor` & `limit` only).

> Shadow mode means **observe-only**: the AI explains but does not take actions—handy for safety & demos.
