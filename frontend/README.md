# 🎨 IntelPulse Frontend (React + Vite + Tailwind CSS)

This is the standalone React frontend for **IntelPulse AI Agent**. It communicates with the Python FastAPI backend via REST API endpoints (`/api/scan`, `/api/chat`, `/api/health`).

---

## 🚀 Quick Setup for Frontend Developer

### 1. Install Dependencies
Navigate into the `frontend` folder and install packages:
```bash
cd frontend
npm install
```

### 2. Start Development Server
```bash
npm run dev
```
The React UI will run at `http://localhost:5173`.

---

## 🔗 Backend API Connection (`src/api.js`)

By default, the frontend connects to `http://localhost:8000`.

To point to a live production FastAPI backend (e.g. deployed on Render), set `VITE_API_URL` in `.env`:
```env
VITE_API_URL=https://your-fastapi-backend.onrender.com
```

### Key API Endpoints Used:
- `GET /api/health` -> Backend status and whether Gemini synthesis is active (`llm_active`).
- `POST /api/scan/stream` -> Primary scan path. Streams the agent trace as NDJSON, one JSON event per line (`step_start`, `step_complete`, `memory_recall`, `memory_update`, `final_complete`).
- `POST /api/scan` -> Buffered scan. Used automatically as the fallback when the stream fails.
- `POST /api/chat` -> Analyst follow-up. Send the findings currently on screen as `context_*` arrays so the answer stays grounded in real retrieved data.

`competitors` is a **comma-separated string** (e.g. `"Sarvam, OpenAI, Google"`), not an array.

---

## 🌐 1-Click Deployment to Vercel

1. Push the `frontend` folder to GitHub.
2. Log into [Vercel.com](https://vercel.com).
3. Click **Add New Project**, import your repository, and select `frontend` as the **Root Directory**.
4. Set Environment Variable: `VITE_API_URL = https://your-backend-url.com`.
5. Click **Deploy!**
