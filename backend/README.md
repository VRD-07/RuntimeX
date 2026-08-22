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

For dependable Indian patent coverage also set `EPO_OPS_KEY` / `EPO_OPS_SECRET` (free registration at [developers.epo.org](https://developers.epo.org)). EPO OPS is the only official patent API still reachable that indexes Indian publications — PatentsView was retired and the USPTO Open Data Portal is US-only and key-gated. Without those two variables the patent tool falls back to keyless tiers that throttle aggressively, and it reports coverage as *unavailable* rather than claiming no patents exist.

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

`/api/scan` accepts `topic`, `competitors` (a **comma-separated string**, e.g. `"Sarvam, OpenAI, Google"`), `max_items` (1–10), `max_steps` (1–30, default 18) and `model`. A non-Gemini `model` is logged and resolved to `GEMINI_MODEL` rather than rejected.

`max_steps` bounds **tool calls only** — the two analyst steps sit outside that budget. The initial scan issues 4 calls per competitor (news, model hub, Reddit, Hacker News) plus 3 topic-level calls, so the default clears `4 * N + 3` for a three-competitor scan.

Responses carry both `structured_output.sections` (grouped, the shape the UI renders) and the flat legacy arrays `news`, `papers`, `patents`, `github_repos`, `reddit_posts`, `hf_models`, `hn_posts`. Both are derived from `SECTION_RESPONSE_KEYS` in `agent_brain.py`, so adding a source in one place cannot silently drop it from the other.

---

## 🧪 Tests

```bash
python test_patent_parsers.py
```
**Offline.** Exercises the EPO OPS and Google Patents response parsers against fixtures reproducing the real response shapes. Needed because every keyless patent endpoint now throttles, so a live patent test proves only that the network refused us.

```bash
python test_audit_tools.py
```
**Live.** Contract smoke test across all seven tools — each must return `{"text", "items", "source_type"}` with fully-populated item metadata, and every `SECTION_ORDER` source type must be covered. Exits non-zero on a violation.

```bash
python test_standalone_queries.py
```
**Live.** Query-coverage probe across several real phrasings per tool.

```bash
python verify_e2e.py http://127.0.0.1:8000
```
**Live, needs a running server.** Drives `/api/scan/stream` the way the browser does and asserts the contract the UI depends on: NDJSON parses line by line, every `step_start` is paired with a `step_complete`, every source type reaches `structured_output.sections`, each section matches its flat array, every finding carries a real `http(s)` URL, and `/api/chat` accepts the new `context_*` arrays.

---

## 🌐 Deployment to Render

1. Deploy this repository as a **Web Service** with **Root Directory** `backend`.
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Set `GEMINI_API_KEY` in the Render dashboard (plus any optional source keys — `EPO_OPS_KEY`/`EPO_OPS_SECRET` matter most, since a shared host IP is throttled by the keyless patent tiers far sooner than a laptop is).
5. Set `ALLOWED_ORIGIN_REGEX` if your frontend is not on this project's Vercel domain — the default regex will otherwise block it.
6. Attach a persistent disk and set `MEMORY_DB_PATH` to a path on it. Render's default filesystem is ephemeral, so long-term scan memory resets on each deploy without this.
