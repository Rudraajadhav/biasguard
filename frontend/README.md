# BiasGuard Frontend

Dark-themed React frontend for BiasGuard. React + Vite + Tailwind + Framer Motion.

## Setup

```bash
cd frontend
npm install
```

## Run (development)

The backend must be running first (port 8000):

```bash
# terminal 1 — backend
cd backend
uvicorn main:app --reload

# terminal 2 — frontend
cd frontend
npm run dev
```

Then open the URL Vite prints — usually **http://localhost:5173**

## Build for production

```bash
npm run build      # outputs to dist/
npm run preview    # preview the production build
```

## Structure

| Path | What |
|------|------|
| `src/App.jsx` | Routing + auth gate |
| `src/lib/api.js` | Backend API client |
| `src/components/UI.jsx` | Shared components (logo, animated number, bias bar, etc.) |
| `src/pages/Auth.jsx` | Login / signup |
| `src/pages/AppShell.jsx` | Sidebar layout for logged-in pages |
| `src/pages/Trades.jsx` | Trade logging |
| `src/pages/Report.jsx` | Bias report with charts |

## Design

- **Fonts**: Fraunces (display), IBM Plex Sans (body), IBM Plex Mono (numbers)
- **Theme**: dark fintech — deep ink background, mint accent, amber/coral for warnings
- **Motion**: Framer Motion — staggered page loads, counting numbers, filling bars

## Notes

- The API base URL is `http://localhost:8000` — set in `src/lib/api.js`.
  Change it there when you deploy.
- Auth token is stored in `localStorage`.
