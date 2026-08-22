import os
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from agent_brain import AutonomousReActAgent, TOOL_REGISTRY, FieldAgent
from tools.research_tool import search_semantic_scholar
from tools.patent_tool import search_patents
from tools.competitor_tool import search_news
from tools.github_tool import search_github
from tools.reddit_tool import search_reddit

load_dotenv()

app = FastAPI(
    title="IntelPulse ReAct Autonomous Agent API",
    description="Autonomous Research & Competitor Tracking Agent adhering to strict ReAct Grounded Reasoning format.",
    version="2.1.0"
)

# CORS Configuration
raw_allowed_origins = os.getenv("ALLOWED_ORIGINS", "")
origins_list = [o.strip().rstrip("/") for o in raw_allowed_origins.split(",") if o.strip()]

default_explicit_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]

explicit_cors_origins = list(dict.fromkeys(default_explicit_origins + origins_list))

app.add_middleware(
    CORSMiddleware,
    allow_origins=explicit_cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept", "Origin", "X-Requested-With"],
)

# Pydantic Schemas
class ScanRequest(BaseModel):
    topic: str = Field(default="Regional language capabilities for AI", description="Research topic or domain to scan")
    competitors: str = Field(default="Sarvam, OpenAI, Google", description="Competitor names or keywords")
    max_items: int = Field(default=5, ge=1, le=10, description="Items to fetch per source")
    model: Optional[str] = Field(default="claude-3-5-sonnet", description="Model choice")

class ScanResponse(BaseModel):
    status: str
    topic: str
    competitors: str
    structured_output: Optional[Dict[str, Any]] = None
    final_answer: str
    executive_report: str
    papers: List[Dict[str, Any]]
    news: List[Dict[str, Any]]
    patents: Optional[List[Dict[str, Any]]] = []
    github_repos: Optional[List[Dict[str, Any]]] = []
    trace: List[Dict[str, Any]]
    memory_recall: Optional[Dict[str, Any]] = None
    agentrouter_active: bool

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    question: str
    chat_history: Optional[List[ChatMessage]] = []
    context_research: List[Dict[str, Any]] = []
    context_competitors: List[Dict[str, Any]] = []
    model: Optional[str] = "claude-3-5-sonnet"

class ChatResponse(BaseModel):
    answer: str
    status: str
    tool_executed: Optional[Dict[str, Any]] = None

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
    api_key_present = bool(os.getenv("GEMINI_API_KEY", "").strip() or os.getenv("AGENTROUTER_API_KEY", "").strip())
    return {
        "status": "healthy",
        "agentrouter_active": api_key_present,
        "engine_mode": "Gemini 2.5 ReAct" if api_key_present else "Fallback Grounded ReAct",
        "tools_loaded": list(TOOL_REGISTRY.keys())
    }

@app.post("/api/scan/stream")
def stream_autonomous_scan(request: ScanRequest):
    """
    Real-time Dynamic Streaming Endpoint:
    Yields memory recall, agent thoughts, actions, observations, and final reports line-by-line as NDJSON.
    """
    agent = AutonomousReActAgent(model=request.model)
    return StreamingResponse(
        agent.stream_scan(topic=request.topic, competitors=request.competitors, max_items=request.max_items),
        media_type="application/x-ndjson"
    )

@app.post("/api/scan", response_model=ScanResponse)
def run_autonomous_scan(request: ScanRequest):
    """
    Frontend Integration Endpoint: Executes Autonomous ReAct Agent Scan.
    """
    try:
        agent = AutonomousReActAgent(model=request.model)
        result = agent.run_scan(topic=request.topic, competitors=request.competitors, max_items=request.max_items, max_steps=12)
        
        return ScanResponse(
            status="success",
            topic=request.topic,
            competitors=request.competitors,
            papers=[],
            news=[],
            executive_report=result["executive_report"],
            trace=result["trace"],
            memory_recall=result.get("memory_recall"),
            agentrouter_active=result["agentrouter_active"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat", response_model=ChatResponse)
def analyst_chat(request: ChatRequest):
    """
    Analyst Q&A Chat endpoint with Multi-Turn Memory & Field Agent Targeted Tool Execution.
    - Preserves prior conversation turns (chat_history).
    - If user asks a targeted follow-up (e.g. 'patent', 'news', 'github'), triggers 1 Field Agent tool call.
    - Tags follow-up tool call in trace with trigger='user_followup'.
    """
    try:
        field_agent = FieldAgent(model=request.model)
        tool_res = None
        
        # Check if question requires a fresh targeted tool call
        q_lower = request.question.lower()
        trigger_keywords = ["patent", "news", "funding", "github", "code", "reddit", "sentiment", "user feedback", "paper"]
        
        if any(kw in q_lower for kw in trigger_keywords):
            tool_res = field_agent.execute_targeted_followup(request.question, max_items=3)
            tool_res["trigger"] = "user_followup"
            tool_res["agent_role"] = "Field Agent"

        # Build stateful prompt with full chat history
        history_context = ""
        if request.chat_history:
            history_context = "\n\nCONVERSATION HISTORY:\n" + "\n".join([
                f"{msg.role.upper()}: {msg.content}" for msg in request.chat_history[-6:]
            ])

        tool_context = ""
        if tool_res:
            tool_context = f"\n\nREAL-TIME TARGETED FIELD OBSERVATION (Triggered by follow-up):\nAction: {tool_res['action']}\nObservation:\n{tool_res['observation']}"

        prompt = (
            f"You are the Strategic Analyst Agent responding to a follow-up question."
            f"{history_context}"
            f"{tool_context}\n\n"
            f"USER FOLLOW-UP QUESTION: {request.question}\n"
            f"Provide a concise 2-4 sentence analytical answer citing the grounded data."
        )

        # Execute LLM Answer Synthesis
        api_key = os.getenv('GEMINI_API_KEY', '')
        model_name = request.model or os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')

        import logging
        import google.generativeai as genai

        chat_logger = logging.getLogger("main")
        chat_logger.info("=== [GEMINI CHAT LLM API REQUEST START] ===")
        chat_logger.info(f"[Model Name]: '{model_name}'")
        chat_logger.info(f"[API Key Check]: Non-empty={bool(api_key)}, Key Length={len(api_key)}")

        answer_text = ""
        if api_key:
            try:
                genai.configure(api_key=api_key)
                try:
                    g_model = genai.GenerativeModel(
                        model_name=model_name,
                        system_instruction="You are the Strategic Analyst Agent handling user follow-up questions with grounded memory."
                    )
                    response = g_model.generate_content(prompt)
                except Exception:
                    g_model = genai.GenerativeModel(
                        model_name="gemini-1.5-flash",
                        system_instruction="You are the Strategic Analyst Agent handling user follow-up questions with grounded memory."
                    )
                    response = g_model.generate_content(prompt)

                chat_logger.info("=== [GEMINI CHAT LLM API RESPONSE RECEIVED] ===")
                chat_logger.info(f"[Raw Response Text]: {response.text}")
                if response.text:
                    answer_text = response.text.strip()
            except Exception as e:
                chat_logger.error("=== [GEMINI CHAT LLM API EXCEPTION] ===", exc_info=True)
                chat_logger.error(f"[Chat API Exception Detail]: {e}")

        if not answer_text:
            if tool_res:
                answer_text = f"Based on the real-time targeted field lookup (`{tool_res['action']}`), here are the latest observations:\n\n{tool_res['observation'][:400]}..."
            else:
                answer_text = f"Analyst Response to '{request.question}': Based on the retrieved intelligence observations, the competitive density remains focused across key technical benchmarks."

        return ChatResponse(
            answer=answer_text,
            status="success",
            tool_executed=tool_res
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run("main:app", host=host, port=port, reload=True)
