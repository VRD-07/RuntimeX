import os
import logging
import sys
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from agent_brain import (
    AutonomousReActAgent,
    FieldAgent,
    TOOL_REGISTRY,
    DEFAULT_GEMINI_MODEL,
    SUPPORTED_GEMINI_MODELS,
    GENAI_AVAILABLE,
    format_context_items,
    llm_available,
    resolve_model,
    synthesize_chat_answer,
)

load_dotenv()

# ---------------------------------------------------------------------------
# Logging
#
# Configured here only, because this module is the application entrypoint;
# library modules just call getLogger(__name__). Tool output is arbitrary text
# from third-party APIs, so the stream handler must tolerate characters the
# console codec cannot represent — on a Windows cp1252 console an unescaped
# curly quote in a news headline would otherwise raise UnicodeEncodeError
# mid-request and turn a successful scan into a 500.
# ---------------------------------------------------------------------------
_log_stream = sys.stdout
try:
    _log_stream.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):  # pragma: no cover - non-reconfigurable stream
    pass

_handler = logging.StreamHandler(_log_stream)
_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[_handler], force=True)
logger = logging.getLogger("intelpulse.api")

app = FastAPI(
    title="IntelPulse ReAct Autonomous Agent API",
    description="Autonomous Research & Competitor Tracking Agent adhering to strict ReAct Grounded Reasoning format.",
    version="2.2.0"
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
raw_allowed_origins = os.getenv("ALLOWED_ORIGINS", "")
origins_list = [o.strip().rstrip("/") for o in raw_allowed_origins.split(",") if o.strip()]

default_explicit_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]
explicit_cors_origins = list(dict.fromkeys(default_explicit_origins + origins_list))

# Scoped to this project's Vercel deployments (including preview URLs) rather than every
# *.vercel.app host. Override with ALLOWED_ORIGIN_REGEX if the project is renamed.
DEFAULT_ORIGIN_REGEX = r"^https://runtime-x[a-z0-9-]*\.vercel\.app$"
cors_origin_regex = os.getenv("ALLOWED_ORIGIN_REGEX", "").strip() or DEFAULT_ORIGIN_REGEX

app.add_middleware(
    CORSMiddleware,
    allow_origins=explicit_cors_origins,
    allow_origin_regex=cors_origin_regex,
    # No cookie or HTTP-auth flows exist on this API, so credentialed cross-origin
    # requests are not permitted. Bearer tokens in Authorization still work.
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept", "Origin", "X-Requested-With"],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class ScanRequest(BaseModel):
    topic: str = Field(default="Regional language capabilities for AI", description="Research topic or domain to scan")
    competitors: str = Field(default="Sarvam, OpenAI, Google", description="Comma-separated competitor names or keywords")
    max_items: int = Field(default=5, ge=1, le=10, description="Items to fetch per source")
    # Bounds tool calls only; the two analyst steps sit outside this budget. The
    # initial scan issues 4 calls per competitor plus 3 topic-level calls, so the
    # default has to clear 4*N + 3.
    max_steps: int = Field(default=18, ge=1, le=30, description="Maximum number of grounded tool calls per scan")
    model: Optional[str] = Field(default=DEFAULT_GEMINI_MODEL, description="Gemini model id used for synthesis")
    # Deliberate fault injection for the adversarial demo. Comma-separated; only
    # 'tool_failure', 'conflicting_evidence' and 'budget_exhaustion' are honoured,
    # and nothing activates unless this is explicitly sent.
    chaos_mode: Optional[str] = Field(default=None, description="Comma-separated chaos modes, e.g. 'tool_failure'")


class ScanResponse(BaseModel):
    status: str
    topic: str
    competitors: str
    structured_output: Optional[Dict[str, Any]] = None
    final_answer: str
    executive_report: str
    gap_report: List[Dict[str, Any]] = []
    papers: List[Dict[str, Any]] = []
    news: List[Dict[str, Any]] = []
    patents: List[Dict[str, Any]] = []
    github_repos: List[Dict[str, Any]] = []
    reddit_posts: List[Dict[str, Any]] = []
    hf_models: List[Dict[str, Any]] = []
    hn_posts: List[Dict[str, Any]] = []
    trace: List[Dict[str, Any]] = []
    memory_recall: Optional[Dict[str, Any]] = None
    llm_active: bool
    model_used: str


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, description="Analyst follow-up question")
    chat_history: Optional[List[ChatMessage]] = []
    context_research: List[Dict[str, Any]] = []
    context_competitors: List[Dict[str, Any]] = []
    context_patents: List[Dict[str, Any]] = []
    context_github: List[Dict[str, Any]] = []
    context_reddit: List[Dict[str, Any]] = []
    context_models: List[Dict[str, Any]] = []
    context_hackernews: List[Dict[str, Any]] = []
    model: Optional[str] = DEFAULT_GEMINI_MODEL


class ChatResponse(BaseModel):
    answer: str
    status: str
    tool_executed: Optional[Dict[str, Any]] = None
    llm_active: bool


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/")
def read_root():
    return {
        "message": "⚡ IntelPulse ReAct Autonomous Agent API is running!",
        "documentation": "/docs",
        "health": "/api/health",
        "available_tools": list(TOOL_REGISTRY.keys())
    }


@app.get("/api/health")
def health_check():
    active = llm_available()
    return {
        "status": "healthy",
        "llm_active": active,
        # Deprecated alias retained so older cached frontend builds keep working.
        "agentrouter_active": active,
        "engine_mode": f"{resolve_model(None)} synthesis" if active else "Deterministic rule-based fallback",
        "sdk_installed": GENAI_AVAILABLE,
        "api_key_configured": bool(os.getenv("GEMINI_API_KEY", "").strip()),
        "supported_models": sorted(SUPPORTED_GEMINI_MODELS),
        "tools_loaded": list(TOOL_REGISTRY.keys())
    }


def _chaos_modes(request: ScanRequest, query_override: Optional[str]) -> List[str]:
    """
    Resolves chaos modes from the query string or the body, query string winning.
    The query form exists so a live demo can flip the switch from the URL bar
    without editing a request payload.
    """
    raw = query_override if query_override is not None else request.chaos_mode
    return [m for m in (raw or "").split(",") if m.strip()]


@app.post("/api/scan/stream")
def stream_autonomous_scan(request: ScanRequest, chaos_mode: Optional[str] = None):
    """
    Real-time streaming endpoint.
    Yields memory recall, agent thoughts, actions, observations, and the final report as NDJSON.
    """
    agent = AutonomousReActAgent(model=request.model, chaos_modes=_chaos_modes(request, chaos_mode))
    return StreamingResponse(
        agent.stream_scan(
            topic=request.topic,
            competitors=request.competitors,
            max_items=request.max_items,
            max_steps=request.max_steps,
        ),
        media_type="application/x-ndjson"
    )


@app.post("/api/scan", response_model=ScanResponse)
def run_autonomous_scan(request: ScanRequest, chaos_mode: Optional[str] = None):
    """
    Non-streaming scan endpoint. Runs the full orchestration and returns the complete result.
    Also serves as the frontend's fallback when the streaming connection fails.
    """
    try:
        agent = AutonomousReActAgent(model=request.model, chaos_modes=_chaos_modes(request, chaos_mode))
        result = agent.run_scan(
            topic=request.topic,
            competitors=request.competitors,
            max_items=request.max_items,
            max_steps=request.max_steps,
        )

        return ScanResponse(
            status="success",
            topic=result["topic"],
            competitors=result["competitors"],
            structured_output=result["structured_output"],
            final_answer=result["final_answer"],
            executive_report=result["executive_report"],
            gap_report=result.get("gap_report", []),
            papers=result.get("papers", []),
            news=result.get("news", []),
            patents=result.get("patents", []),
            github_repos=result.get("github_repos", []),
            reddit_posts=result.get("reddit_posts", []),
            hf_models=result.get("hf_models", []),
            hn_posts=result.get("hn_posts", []),
            trace=result.get("trace", []),
            memory_recall=result.get("memory_recall"),
            llm_active=result.get("llm_active", False),
            model_used=result.get("model_used", ""),
        )
    except Exception as e:
        logger.exception("Scan failed")
        raise HTTPException(status_code=500, detail=f"Scan failed: {e}")


@app.post("/api/chat", response_model=ChatResponse)
def analyst_chat(request: ChatRequest):
    """
    Analyst Q&A endpoint with multi-turn memory, scan-grounded context, and targeted tool execution.
    - Preserves prior conversation turns (chat_history).
    - Grounds the answer in the findings the frontend retrieved during the scan.
    - Targeted follow-ups (e.g. 'patent', 'news', 'github') trigger one live Field Agent tool call.
    """
    try:
        field_agent = FieldAgent(model=request.model)
        tool_res = None

        q_lower = request.question.lower()
        trigger_keywords = ["patent", "news", "funding", "github", "code", "reddit", "sentiment", "user feedback", "paper"]

        if any(kw in q_lower for kw in trigger_keywords):
            tool_res = field_agent.execute_targeted_followup(request.question, max_items=3)
            tool_res["trigger"] = "user_followup"
            tool_res["agent_role"] = "Field Agent"

        # Ground the answer in the scan findings the client is displaying
        context_blocks = "".join([
            format_context_items("NEWS FINDINGS", request.context_competitors),
            format_context_items("RESEARCH FINDINGS", request.context_research),
            format_context_items("PATENT FINDINGS", request.context_patents),
            format_context_items("GITHUB FINDINGS", request.context_github),
            format_context_items("REDDIT COMMUNITY FINDINGS", request.context_reddit),
            format_context_items("PUBLISHED MODEL TRACTION (HUGGING FACE)", request.context_models),
            format_context_items("HACKER NEWS ENGAGEMENT", request.context_hackernews),
        ])

        history = [m.model_dump() for m in (request.chat_history or [])]
        answer_text = synthesize_chat_answer(
            question=request.question,
            chat_history=history,
            context_blocks=context_blocks,
            tool_res=tool_res,
            model=request.model,
        )

        if not answer_text:
            # Deterministic fallback: report real retrieved data, never invented analysis.
            if tool_res and tool_res["items"]:
                titles = "\n".join(f"- {i['title']} ({i.get('source_name', 'source')})" for i in tool_res["items"][:3])
                answer_text = (
                    f"LLM synthesis is unavailable, so here is the raw result of the live "
                    f"`{tool_res['action']}` lookup:\n\n{titles}"
                )
            elif context_blocks:
                answer_text = (
                    "LLM synthesis is unavailable, so no narrative answer can be generated. "
                    f"The scan findings currently loaded are:{context_blocks[:800]}"
                )
            else:
                answer_text = (
                    "LLM synthesis is unavailable and no scan findings are loaded yet. "
                    "Run a scan first, then ask again."
                )

        return ChatResponse(
            answer=answer_text,
            status="success",
            tool_executed=tool_res,
            llm_active=llm_available(),
        )
    except Exception as e:
        logger.exception("Chat request failed")
        raise HTTPException(status_code=500, detail=f"Chat failed: {e}")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    # reload is a development convenience; Render/production should run uvicorn directly.
    uvicorn.run("main:app", host=host, port=port, reload=os.getenv("UVICORN_RELOAD", "").lower() == "true")

# End of application
