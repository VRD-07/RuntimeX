import os
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from tools.research_tool import fetch_arxiv_papers
from tools.competitor_tool import fetch_competitor_news
from agent_brain import AgentRouterBrain

load_dotenv()

app = FastAPI(
    title="IntelPulse AI Agent API",
    description="Autonomous Research & Competitor Tracking Backend powered by AgentRouter Claude",
    version="1.0.0"
)

# Enable CORS for decoupled React Frontend development & deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows local React dev server (e.g. http://localhost:5173) & Vercel
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request & Response Schemas
class ScanRequest(BaseModel):
    topic: str = Field(default="Agentic AI Frameworks", description="Research topic or domain to scan")
    competitors: str = Field(default="OpenAI, Anthropic, DeepMind", description="Competitor names or keywords")
    max_items: int = Field(default=5, ge=1, le=10, description="Items to fetch per source")
    model: Optional[str] = Field(default="claude-3-5-sonnet", description="Claude model choice")

class ScanResponse(BaseModel):
    status: str
    topic: str
    competitors: str
    papers: List[Dict[str, Any]]
    news: List[Dict[str, Any]]
    executive_report: str
    agentrouter_active: bool

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
        "message": "⚡ IntelPulse AI Agent API is running!",
        "documentation": "/docs",
        "health": "/api/health"
    }

@app.get("/api/health")
def health_check():
    api_key_present = bool(os.getenv("AGENTROUTER_API_KEY", "").strip())
    return {
        "status": "healthy",
        "agentrouter_active": api_key_present,
        "engine_mode": "Claude API" if api_key_present else "Fallback Engine"
    }

@app.post("/api/scan", response_model=ScanResponse)
def run_autonomous_scan(request: ScanRequest):
    try:
        # Fetch ArXiv papers and DuckDuckGo market news concurrently/sequentially
        papers = fetch_arxiv_papers(request.topic, max_results=request.max_items)
        news = fetch_competitor_news(request.competitors, max_results=request.max_items)
        
        # Initialize Agent Brain
        brain = AgentRouterBrain(model=request.model)
        
        # Generate Executive Synthesis Report
        report = brain.generate_executive_digest(
            research_data=papers,
            competitor_data=news,
            topic=f"{request.topic} & {request.competitors}"
        )
        
        return ScanResponse(
            status="success",
            topic=request.topic,
            competitors=request.competitors,
            papers=papers,
            news=news,
            executive_report=report,
            agentrouter_active=bool(brain.api_key)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat", response_model=ChatResponse)
def analyst_chat(request: ChatRequest):
    try:
        brain = AgentRouterBrain(model=request.model)
        answer = brain.ask_analyst_chat(
            user_question=request.question,
            context_research=request.context_research,
            context_competitors=request.context_competitors
        )
        return ChatResponse(answer=answer, status="success")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run("main:app", host=host, port=port, reload=True)
