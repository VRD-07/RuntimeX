import os
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from agent_brain import AutonomousReActAgent, TOOL_REGISTRY
from tools.research_tool import search_semantic_scholar
from tools.patent_tool import search_patents
from tools.competitor_tool import search_news
from tools.github_tool import search_github
from tools.reddit_tool import search_reddit

load_dotenv()

app = FastAPI(
    title="IntelPulse ReAct Autonomous Agent API",
    description="Autonomous Research & Competitor Tracking Agent adhering to strict ReAct Grounded Reasoning format.",
    version="2.0.0"
)

# CORS Configuration - Explicit origins for local development & Vercel deployment
raw_allowed_origins = os.getenv("ALLOWED_ORIGINS", "")
origins_list = [o.strip().rstrip("/") for o in raw_allowed_origins.split(",") if o.strip()]

default_explicit_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]

# Combine explicit default local origins + env-configured Vercel origins
explicit_cors_origins = list(dict.fromkeys(default_explicit_origins + origins_list))

app.add_middleware(
    CORSMiddleware,
    allow_origins=explicit_cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept", "Origin", "X-Requested-With"],
)

@app.on_event("startup")
def log_cors_configuration():
    import logging
    logger = logging.getLogger("uvicorn")
    logger.info(f"[CORS STARTUP LOG] Configured Explicit Allowed Origins: {explicit_cors_origins}")
    logger.info("[CORS STARTUP LOG] Configured Allowed Origin Regex: https://.*\\.vercel\\.app")

# Pydantic Schemas
class ScanRequest(BaseModel):
    topic: str = Field(default="Dating Apps", description="Research topic or domain to scan")
    competitors: str = Field(default="Tinder, Bumble", description="Competitor names or keywords")
    max_items: int = Field(default=5, ge=1, le=10, description="Items to fetch per source")
    model: Optional[str] = Field(default="claude-3-5-sonnet", description="Claude model choice")

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
    agentrouter_active: bool

class AgentRunRequest(BaseModel):
    user_request: str
    model: Optional[str] = "claude-3-5-sonnet"
    max_steps: Optional[int] = 5

class ChatRequest(BaseModel):
    question: str
    context_research: List[Dict[str, Any]] = []
    context_competitors: List[Dict[str, Any]] = []
    model: Optional[str] = "claude-3-5-sonnet"

class ChatResponse(BaseModel):
    answer: str
    status: str

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
    api_key_present = bool(os.getenv("AGENTROUTER_API_KEY", "").strip())
    return {
        "status": "healthy",
        "agentrouter_active": api_key_present,
        "engine_mode": "AgentRouter Claude ReAct" if api_key_present else "Fallback Grounded ReAct",
        "tools_loaded": list(TOOL_REGISTRY.keys())
    }

@app.post("/api/scan/stream")
def stream_autonomous_scan(request: ScanRequest):
    """
    Real-time Dynamic Streaming Endpoint:
    Yields agent thoughts, actions, observations, and final reports line-by-line as NDJSON.
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
    Gathers Semantic Scholar papers, News, Patents, and GitHub activity.
    """
    try:
        agent = AutonomousReActAgent(model=request.model)
        result = agent.run_scan(topic=request.topic, competitors=request.competitors, max_items=request.max_items, max_steps=12)
        
        # Structure cards for Frontend Display
        papers_obs = search_semantic_scholar(f"{request.topic} recommendation matching algorithm", max_results=request.max_items)
        news_obs = search_news(f"{request.competitors} {request.topic} news", max_results=request.max_items)
        
        # Simple parser for structured cards in Frontend
        papers = []
        for line in papers_obs.split("- Title: ")[1:]:
            parts = line.split("\n")
            title_year = parts[0] if len(parts) > 0 else "Paper Title"
            abstract = parts[2].replace("Abstract Snippet: ", "").strip() if len(parts) > 2 else "Abstract"
            url = parts[3].replace("URL: ", "").strip() if len(parts) > 3 else "#"
            papers.append({
                "title": title_year.split(" (")[0],
                "published": title_year.split(" (")[1].split(")")[0] if "(" in title_year else "Recent",
                "authors": ["Semantic Scholar Research"],
                "summary": abstract,
                "pdf_url": url
            })

        news = []
        for line in news_obs.split("- Title: ")[1:]:
            parts = line.split("\n")
            title_date = parts[0] if len(parts) > 0 else "News Title"
            snippet = parts[1].replace("Snippet: ", "").strip() if len(parts) > 1 else "Snippet"
            url = parts[2].replace("URL: ", "").strip() if len(parts) > 2 else "#"
            news.append({
                "title": title_date.split(" (Date:")[0],
                "source_name": title_date.split("Source: ")[1].replace(")", "") if "Source: " in title_date else "Web News",
                "date": "Recent",
                "snippet": snippet,
                "url": url
            })

        return ScanResponse(
            status="success",
            topic=request.topic,
            competitors=request.competitors,
            papers=papers if papers else [{"title": f"Recent Literature in {request.topic}", "published": "2026", "authors": ["Academic Search"], "summary": "Algorithmic research paper.", "pdf_url": "https://arxiv.org"}],
            news=news if news else [{"title": f"{request.competitors} Market Signals", "source_name": "Web News", "date": "2026", "snippet": "Market update.", "url": "https://news.google.com"}],
            executive_report=result["final_answer"],
            trace=result["trace"],
            agentrouter_active=result["agentrouter_active"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/agent/run")
def run_agent_directly(request: AgentRunRequest):
    """Direct ReAct Agent endpoint."""
    try:
        agent = AutonomousReActAgent(model=request.model)
        return agent.run(user_request=request.user_request, max_steps=request.max_steps)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat", response_model=ChatResponse)
def analyst_chat(request: ChatRequest):
    """Analyst Q&A Chat endpoint."""
    try:
        agent = AutonomousReActAgent(model=request.model)
        # Quick single step QA or ReAct run
        user_prompt = f"Answer this question based on context: {request.question}"
        res = agent.run(user_request=user_prompt, max_steps=2)
        return ChatResponse(answer=res["final_answer"], status="success")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run("main:app", host=host, port=port, reload=True)
