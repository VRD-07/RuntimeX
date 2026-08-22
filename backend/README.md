# ⚙️ IntelPulse Backend (FastAPI + AgentRouter Claude)

This is the standalone Python FastAPI backend for **IntelPulse AI Agent**.

---

## 🚀 Quick Start (Backend)

### 1. Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 2. Set Environment Variables
Create `.env` inside `backend/`:
```env
AGENTROUTER_API_KEY=your_agentrouter_key_here
AGENTROUTER_BASE_URL=https://agentrouter.ai/v1
AGENTROUTER_MODEL=claude-3-5-sonnet
```

### 3. Run FastAPI Server
```bash
uvicorn main:app --reload --port 8000
```
Server runs at `http://localhost:8000`.  
View interactive Swagger API documentation at **`http://localhost:8000/docs`**.

---

## 🌐 1-Click Deployment to Render / Railway / Koyeb

1. Deploy the `backend/` directory to **Render** (as a Web Service).
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Set Environment Variable: `AGENTROUTER_API_KEY` in Render dashboard.
