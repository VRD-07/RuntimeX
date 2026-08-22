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
- `GET /api/health` -> Checks backend status & AgentRouter status.
- `POST /api/scan` -> Runs paper & competitor scan + executive report generation.
- `POST /api/chat` -> Sends user question to AI analyst.

---

## 🌐 1-Click Deployment to Vercel

1. Push the `frontend` folder to GitHub.
2. Log into [Vercel.com](https://vercel.com).
3. Click **Add New Project**, import your repository, and select `frontend` as the **Root Directory**.
4. Set Environment Variable: `VITE_API_URL = https://your-backend-url.com`.
5. Click **Deploy!**
