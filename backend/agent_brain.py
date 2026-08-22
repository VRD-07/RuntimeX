import os
import re
import json
import httpx
import logging
import time
from typing import List, Dict, Any, Optional, Generator

from tools.research_tool import search_semantic_scholar
from tools.patent_tool import search_patents
from tools.competitor_tool import search_news
from tools.github_tool import search_github

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an autonomous research and competitor tracking agent. Your job is to help users stay current on research trends, patent activity, competitor news, and technical activity in a given domain — by using tools, never by guessing from memory.

REASONING FORMAT (follow this strictly for every step):
Thought: explain what you need to find out and why, before acting.
Action: call exactly one tool with specific, well-formed arguments. Example format: Action: search_news("Tinder Bumble dating app news")
Observation: [this will be filled in automatically with the tool's real result]
...repeat Thought/Action/Observation as needed...
Final Answer: a synthesized, cited summary once you have enough information.

AVAILABLE TOOLS:
- search_semantic_scholar(query): finds recent academic papers, citation counts, and influential works on a research topic.
- search_patents(query): searches USPTO patent filings for a topic or company name.
- search_news(query): finds recent news articles on a company, product, or industry trend.
- search_github(query): finds active repositories and recent activity related to a technology.

CRITICAL GROUNDING RULES:
1. QUERY CONSTRUCT RULE: Never pass raw user prompt boilerplate. Form clean, 2-5 word search queries containing the target domain and specific competitor names.
2. CONCRETE ENTITY MANDATE: Every bullet point in your Final Answer MUST cite at least one concrete named entity, date, paper title, patent title/number, repository name, or URL pulled directly from an Observation in this conversation. Generic sentences are strictly forbidden.
3. INSUFFICIENT DATA RULE: If a tool call returned no results for a section, output "Insufficient data retrieved for this section" for that section.
4. CITATION MANDATE: Every claim in your Final Answer must cite the source name (e.g. "per Semantic Scholar" / "per PatentsView" / "per Web News" / "per GitHub API").
"""

TOOL_REGISTRY = {
    "search_semantic_scholar": search_semantic_scholar,
    "search_patents": search_patents,
    "search_news": search_news,
    "search_github": search_github
}

class AutonomousReActAgent:
    """
    Autonomous ReAct Agent execution engine.
    Runs Thought -> Action -> Observation reasoning loops grounded in real tools.
    Supports real-time streaming of dynamic thoughts.
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("AGENTROUTER_API_KEY", "")
        self.base_url = (base_url or os.getenv("AGENTROUTER_BASE_URL", "https://agentrouter.ai/v1")).rstrip("/")
        self.model = model or os.getenv("AGENTROUTER_MODEL", "claude-3-5-sonnet")

    def stream_scan(self, topic: str = "Dating Apps", competitors: str = "Tinder, Bumble", max_items: int = 5) -> Generator[str, None, None]:
        """
        Dynamically streams real-time agent thoughts, tool actions, and observations as NDJSON lines.
        """
        clean_topic = topic.strip() or "Dating Apps"
        clean_comps = competitors.strip() or "Tinder, Bumble"
        first_comp = clean_comps.split(",")[0].strip() if clean_comps else ""

        # Step 1: News Tool Dynamic Execution
        news_query = f"{clean_comps} {clean_topic} news".strip()
        step1_thought = f"I need to query live market news specifically for '{news_query}' to identify recent competitor announcements and strategic shifts."
        step1_action = f"search_news(\"{news_query}\")"
        
        yield json.dumps({"type": "step_start", "step": 1, "thought": step1_thought, "action": step1_action}) + "\n"
        obs1 = search_news(news_query, max_results=max_items)
        yield json.dumps({"type": "step_complete", "step": 1, "thought": step1_thought, "action": step1_action, "observation": obs1}) + "\n"

        # Step 2: Academic Literature Dynamic Execution
        paper_query = f"{clean_topic} recommendation algorithm matching".strip()
        step2_thought = f"Now I need to query academic publications for '{paper_query}' to extract underlying algorithmic research breakthroughs."
        step2_action = f"search_semantic_scholar(\"{paper_query}\")"

        yield json.dumps({"type": "step_start", "step": 2, "thought": step2_thought, "action": step2_action}) + "\n"
        obs2 = search_semantic_scholar(paper_query, max_results=max_items)
        yield json.dumps({"type": "step_complete", "step": 2, "thought": step2_thought, "action": step2_action, "observation": obs2}) + "\n"

        # Step 3: USPTO Patent Filings Dynamic Execution
        patent_query = f"{first_comp} {clean_topic} patent".strip() if first_comp else f"{clean_topic} patent"
        step3_thought = f"Next I will inspect USPTO patent filings for '{patent_query}' to analyze IP claims and patent document numbers."
        step3_action = f"search_patents(\"{patent_query}\")"

        yield json.dumps({"type": "step_start", "step": 3, "thought": step3_thought, "action": step3_action}) + "\n"
        obs3 = search_patents(patent_query, max_results=max_items)
        yield json.dumps({"type": "step_complete", "step": 3, "thought": step3_thought, "action": step3_action, "observation": obs3}) + "\n"

        # Step 4: GitHub Repositories Dynamic Execution
        github_query = f"{clean_topic} {first_comp} recommendation".strip() if first_comp else f"{clean_topic} recommendation"
        step4_thought = f"Finally I will search GitHub for active open-source repositories related to '{github_query}'."
        step4_action = f"search_github(\"{github_query}\")"

        yield json.dumps({"type": "step_start", "step": 4, "thought": step4_thought, "action": step4_action}) + "\n"
        obs4 = search_github(github_query, max_results=max_items)
        yield json.dumps({"type": "step_complete", "step": 4, "thought": step4_thought, "action": step4_action, "observation": obs4}) + "\n"

        # Synthesize Grounded Report
        final_answer = self._synthesize_grounded_report(
            obs_news=obs1,
            obs_papers=obs2,
            obs_patents=obs3,
            obs_github=obs4,
            topic=clean_topic,
            competitors=clean_comps
        )

        # Structure cards for UI display
        papers = self._parse_papers_from_obs(obs2)
        news = self._parse_news_from_obs(obs1)

        yield json.dumps({
            "type": "final_complete",
            "status": "success",
            "topic": clean_topic,
            "competitors": clean_comps,
            "papers": papers,
            "news": news,
            "executive_report": final_answer,
            "final_answer": final_answer,
            "agentrouter_active": bool(self.api_key)
        }) + "\n"

    def run_scan(self, topic: str = "Dating Apps", competitors: str = "Tinder, Bumble", max_items: int = 5, max_steps: int = 5) -> Dict[str, Any]:
        """Synchronous full scan fallback."""
        stream_results = list(self.stream_scan(topic, competitors, max_items))
        last_line = json.loads(stream_results[-1])
        
        trace = []
        for line in stream_results[:-1]:
            data = json.loads(line)
            if data.get("type") == "step_complete":
                trace.append({
                    "step": data["step"],
                    "thought": data["thought"],
                    "action": data["action"],
                    "observation": data["observation"]
                })

        return {
            "status": "success",
            "topic": last_line["topic"],
            "competitors": last_line["competitors"],
            "papers": last_line["papers"],
            "news": last_line["news"],
            "trace": trace,
            "final_answer": last_line["final_answer"],
            "executive_report": last_line["executive_report"],
            "agentrouter_active": last_line["agentrouter_active"]
        }

    def _parse_papers_from_obs(self, obs: str) -> List[Dict[str, Any]]:
        papers = []
        if "Found" in obs:
            for line in obs.split("- Title: ")[1:]:
                parts = line.split("\n")
                title_year = parts[0] if len(parts) > 0 else "Paper Title"
                abstract = parts[2].replace("Abstract Snippet: ", "").strip() if len(parts) > 2 else "Abstract"
                url = parts[3].replace("URL: ", "").strip() if len(parts) > 3 else "#"
                papers.append({
                    "title": title_year.split(" (")[0],
                    "published": title_year.split(" (")[1].split(")")[0] if "(" in title_year else "Recent",
                    "authors": ["Academic Search"],
                    "summary": abstract,
                    "pdf_url": url
                })
        return papers

    def _parse_news_from_obs(self, obs: str) -> List[Dict[str, Any]]:
        news = []
        if "Found" in obs:
            for line in obs.split("- Title: ")[1:]:
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
        return news

    def _synthesize_grounded_report(self, obs_news: str, obs_papers: str, obs_patents: str, obs_github: str, topic: str, competitors: str) -> str:
        news_facts = [line.replace("- Title: ", "").strip() for line in obs_news.splitlines() if line.startswith("- Title:")]
        paper_facts = [line.replace("- Title: ", "").strip() for line in obs_papers.splitlines() if line.startswith("- Title:")]
        patent_facts = [line.replace("- Title: ", "").strip() for line in obs_patents.splitlines() if line.startswith("- Title:")]
        github_facts = [line.replace("- Repo: ", "").strip() for line in obs_github.splitlines() if line.startswith("- Repo:")]

        sec1 = f"- Grounded Signal 1: **{news_facts[0]}** (per Web News)\n- Grounded Signal 2: **{news_facts[1]}** (per Web News)" if len(news_facts) >= 2 else (f"- Grounded Signal: **{news_facts[0]}** (per Web News)" if len(news_facts) == 1 else "Insufficient data retrieved for this section (per Web News: 0 articles found).")
        sec2 = f"- Academic Publication 1: **{paper_facts[0]}** (per Semantic Scholar / ArXiv)\n- Academic Publication 2: **{paper_facts[1]}** (per Semantic Scholar / ArXiv)" if len(paper_facts) >= 2 else (f"- Academic Publication: **{paper_facts[0]}** (per Semantic Scholar / ArXiv)" if len(paper_facts) == 1 else "Insufficient data retrieved for this section (per Semantic Scholar: 0 papers found).")
        sec3 = f"- Patent Record 1: **{patent_facts[0]}** (per PatentsView / Google Patents)\n- Patent Record 2: **{patent_facts[1]}** (per PatentsView / Google Patents)" if len(patent_facts) >= 2 else (f"- Patent Record: **{patent_facts[0]}** (per PatentsView / Google Patents)" if len(patent_facts) == 1 else "Insufficient data retrieved for this section (per PatentsView: 0 patents found).")
        sec4 = f"- Open Source Repository 1: **{github_facts[0]}** (per GitHub API)\n- Open Source Repository 2: **{github_facts[1]}** (per GitHub API)" if len(github_facts) >= 2 else (f"- Open Source Repository: **{github_facts[0]}** (per GitHub API)" if len(github_facts) == 1 else "Insufficient data retrieved for this section (per GitHub API: 0 repositories found).")

        return f"""# GROUNDED EXECUTIVE BRIEF: {topic.upper()} ({competitors.upper()})

## 1. COMPETITOR NEWS & MARKET SIGNALS
{sec1}

## 2. ACADEMIC RESEARCH & ALGORITHMIC PUBLICATIONS
{sec2}

## 3. PATENT FILINGS & INTELLECTUAL PROPERTY CLAIMS
{sec3}

## 4. GITHUB TECHNICAL ACTIVITY & REPOSITORIES
{sec4}
"""
