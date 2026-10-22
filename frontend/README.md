# ChurnWatch AI frontend

React + TypeScript + Vite. Talks to two separate services:
- Main API: `VITE_API_BASE_URL` (default http://127.0.0.1:8001)
- Monitoring API: `VITE_MONITORING_API_BASE_URL` (default http://127.0.0.1:8010).
  In `npm run dev` the browser calls `/monitoring-proxy/...` and Vite forwards it, because Monitoring has no CORS.

Run (PowerShell, inside this folder):
    npm install
    npm run dev       # open http://localhost:5173

Never put API keys or DATABASE_URL in this project. Only VITE_ variables are bundled.
