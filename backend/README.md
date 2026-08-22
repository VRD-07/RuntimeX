# ⚙️ IntelPulse Backend (FastAPI + Google Gemini)

Standalone Python FastAPI backend for **IntelPulse AI Agent**. See the [root README](../README.md) for architecture, the full environment-variable table and deployment details.

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 2. Set Environment Variables
```bash
cp .env.example .env
```
Then add your Gemini key. Only `GEMINI_API_KEY` is required — every other variable is documented inline in `.env.example`:

```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

Without a key the API still starts: tools run normally and a deterministic rule-based analyst replaces LLM synthesis. `llm_active` in every response tells you which path ran.

### 3. Run the Server
```bash
uvicorn main:app --reload --port 8000
```
Server runs at `http://localhost:8000`; Swagger UI at **`http://localhost:8000/docs`**.

---

## 📡 Endpoints

| Method | Path | Purpose |
| :--- | :--- | :--- |
| `GET` | `/` | Service banner |
| `GET` | `/api/health` | `llm_active`, `sdk_installed`, `api_key_configured`, `engine_mode`, `supported_models`, `tools_loaded` |
| `POST` | `/api/scan/stream` | Streams the agent trace as NDJSON (`application/x-ndjson`), one JSON event per line |
| `POST` | `/api/scan` | Same scan, buffered into a single JSON response |
| `POST` | `/api/chat` | Analyst follow-up, grounded in the findings passed as `context_*` arrays |

`/api/scan` accepts `topic`, `competitors` (a **comma-separated string**, e.g. `"Sarvam, OpenAI, Google"`), `max_items` (1–10), `max_steps` (1–24) and `model`. A non-Gemini `model` is logged and resolved to `GEMINI_MODEL` rather than rejected.

---

## 🧪 Tests

Both require network access:

```bash
python test_audit_tools.py
```
Contract smoke test across all five tools — each must return `{"text", "items", "source_type"}` with fully-populated item metadata. Exits non-zero on a violation.

```bash
python test_standalone_queries.py
```
Query-coverage probe across several real phrasings per tool.

---

## 🌐 Deployment to Render

1. Deploy this repository as a **Web Service** with **Root Directory** `backend`.
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Set `GEMINI_API_KEY` in the Render dashboard (plus any optional source keys).
5. Set `ALLOWED_ORIGIN_REGEX` if your frontend is not on this project's Vercel domain — the default regex will otherwise block it.
6. Attach a persistent disk and set `MEMORY_DB_PATH` to a path on it. Render's default filesystem is ephemeral, so long-term scan memory resets on each deploy without this.
