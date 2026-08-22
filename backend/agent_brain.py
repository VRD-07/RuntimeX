import os
import re
import json
import httpx
import logging
from typing import List, Dict, Any, Optional

from tools.research_tool import search_semantic_scholar
from tools.patent_tool import search_patents
from tools.competitor_tool import search_news
from tools.github_tool import search_github

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an autonomous research and competitor tracking agent. Your job is to help users stay current on research trends, patent activity, competitor news, and technical activity in a given domain — by using tools, never by guessing from memory.

REASONING FORMAT (follow this strictly for every step):
Thought: explain what you need to find out and why, before acting.
Action: call exactly one tool with specific, well-formed arguments. Example format: Action: search_patents("automated matching algorithm patent")
Observation: [this will be filled in automatically with the tool's real result]
...repeat Thought/Action/Observation as needed...
Final Answer: a synthesized, cited summary once you have enough information.

AVAILABLE TOOLS:
- search_semantic_scholar(query): finds recent academic papers, citation counts, and influential works on a research topic. Pass concise 2-4 word queries (e.g. search_semantic_scholar("dating preference algorithm")).
- search_patents(query): searches USPTO patent filings for a topic or company name. Pass concise queries (e.g. search_patents("Match Group dating patent")).
- search_news(query): finds recent news articles on a company, product, or industry trend (e.g. search_news("Tinder Bumble news")).
- search_github(query): finds active repositories and recent activity related to a technology (e.g. search_github("dating recommendation engine")).

CRITICAL GROUNDING RULES — these override anything else:
1. QUERY CONSTRUCT RULE: Never pass raw user prompt boilerplate, instructions, or long phrases to tool calls. Form clean, concise, 2-5 word focused queries relevant to that specific tool.
2. CONCRETE ENTITY MANDATE: Every bullet point in your Final Answer MUST cite at least one concrete named entity, date, paper title, patent title/number, repository name, or URL pulled directly from an Observation in this conversation. Generic sentences with no specific facts (e.g. "highlights product iteration and strategic positioning") are STRICTLY FORBIDDEN and treated as a failure state.
3. INSUFFICIENT DATA RULE: If a tool call returned no results or fewer than 2 concrete facts for a section, output "Insufficient data retrieved for this section" for that section instead of generating filler prose.
4. ERROR HONESTY: If a tool returns no results or an error, state that plainly in your next Thought and in the Final Answer. Do NOT invent plausible-sounding results.
5. CITATION MANDATE: Every claim in your Final Answer must cite the source name (e.g. "per Semantic Scholar" / "per PatentsView" / "per Web News" / "per GitHub API") and link/date right next to the claim.
"""

TOOL_REGISTRY = {
    "search_semantic_scholar": search_semantic_scholar,
    "search_patents": search_patents,
    "search_news": search_news,
    "search_github": search_github
}

class AutonomousReActAgent:
    """
    Autonomous ReAct (Reasoning + Acting) Agent execution engine.
    Executes Thought -> Action -> Observation loops using grounded tools.
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("AGENTROUTER_API_KEY", "")
        self.base_url = (base_url or os.getenv("AGENTROUTER_BASE_URL", "https://agentrouter.ai/v1")).rstrip("/")
        self.model = model or os.getenv("AGENTROUTER_MODEL", "claude-3-5-sonnet")

    def run(self, user_request: str, max_steps: int = 5) -> Dict[str, Any]:
        """
        Executes the ReAct loop for a given user request.
        Returns full reasoning trace and grounded final answer.
        """
        if not self.api_key:
            logger.info("No AgentRouter API Key. Executing Fallback Grounded ReAct Loop.")
            return self._run_fallback_loop(user_request)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_request}
        ]

        trace = []
        final_answer = ""

        for step in range(max_steps):
            logger.info(f"--- ReAct Step {step+1}/{max_steps} ---")
            response_text = self._call_llm(messages)
            
            if not response_text:
                logger.warning("Empty response from LLM, falling back.")
                return self._run_fallback_loop(user_request)

            logger.info(f"[LLM RAW RESPONSE]:\n{response_text}")

            # Check if Final Answer is reached
            if "Final Answer:" in response_text:
                parts = response_text.split("Final Answer:", 1)
                thought_part = parts[0].strip()
                final_answer = parts[1].strip()
                if thought_part:
                    trace.append({"step": step + 1, "thought": thought_part, "action": "None", "observation": "Final Answer Generated"})
                break

            # Parse Thought and Action
            thought_match = re.search(r"Thought:(.*?)(?=Action:|$)", response_text, re.DOTALL)
            action_match = re.search(r"Action:\s*([a-zA-Z0-9_]+)\((.*?)\)", response_text, re.DOTALL)

            thought_str = thought_match.group(1).strip() if thought_match else response_text.strip()
            
            if action_match:
                tool_name = action_match.group(1).strip()
                raw_arg = action_match.group(2).strip().strip('"\'')

                # Clean query construction rule check
                clean_query = self._sanitize_tool_query(raw_arg)

                if tool_name in TOOL_REGISTRY:
                    logger.info(f"Executing Tool: {tool_name}('{clean_query}')")
                    observation = TOOL_REGISTRY[tool_name](clean_query)
                else:
                    observation = f"[Error]: Tool '{tool_name}' not recognized. Available tools: {list(TOOL_REGISTRY.keys())}"

                step_record = {
                    "step": step + 1,
                    "thought": thought_str,
                    "action": f"{tool_name}(\"{clean_query}\")",
                    "observation": observation
                }
                trace.append(step_record)

                # Feed observation back into conversation context
                messages.append({"role": "assistant", "content": response_text})
                messages.append({"role": "user", "content": f"Observation: {observation}"})
            else:
                trace.append({"step": step + 1, "thought": thought_str, "action": "None", "observation": "Completed"})
                final_answer = response_text.replace("Thought:", "").strip()
                break

        if not final_answer and trace:
            final_answer = trace[-1].get("observation", "Search completed.")

        return {
            "status": "success",
            "user_request": user_request,
            "model": self.model,
            "trace": trace,
            "final_answer": final_answer,
            "agentrouter_active": True
        }

    def _sanitize_tool_query(self, query: str) -> str:
        """Strips out boilerplate user instructions and keeps concise, focused search terms."""
        cleaned = re.sub(r"(?i)(track|research|patents?|news|github|activity|for|and|recent|trends?|filings?|articles?|repositories|find|search|get|show|me)", "", query)
        cleaned = re.sub(r"[^\w\s]", " ", cleaned).strip()
        words = [w for w in cleaned.split() if len(w) > 1]
        return " ".join(words[:3]) if words else "Dating Apps"

    def _call_llm(self, messages: List[Dict[str, str]]) -> Optional[str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        endpoint = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 1500
        }

        try:
            with httpx.Client(timeout=35.0) as client:
                resp = client.post(endpoint, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        return data["choices"][0]["message"]["content"]
                    elif "content" in data and isinstance(data["content"], list):
                        return data["content"][0].get("text", "")
                else:
                    logger.warning(f"LLM API Error {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.error(f"Failed LLM API call: {e}")
        return None

    def _run_fallback_loop(self, user_request: str) -> Dict[str, Any]:
        """
        Executes a deterministic grounded ReAct trace using clean, focused tool queries
        when running offline or without an API key.
        """
        domain_query = self._sanitize_tool_query(user_request) or "Dating Apps"
        
        # 1. News Tool Call (Focused on Market/Competitors)
        news_query = f"{domain_query} news"
        obs1 = search_news(news_query)
        trace1 = {
            "step": 1,
            "thought": f"I need to query news articles for '{news_query}' to identify concrete company announcements and dates.",
            "action": f"search_news(\"{news_query}\")",
            "observation": obs1
        }

        # 2. Semantic Scholar Tool Call (Focused on Academic Literature)
        paper_query = f"{domain_query} recommendation algorithm"
        obs2 = search_semantic_scholar(paper_query)
        trace2 = {
            "step": 2,
            "thought": f"Now I need to search academic publications for '{paper_query}' to extract concrete paper titles and authors.",
            "action": f"search_semantic_scholar(\"{paper_query}\")",
            "observation": obs2
        }

        # 3. Patent Tool Call (Focused on IP & USPTO Filings)
        patent_query = f"{domain_query} patent"
        obs3 = search_patents(patent_query)
        trace3 = {
            "step": 3,
            "thought": f"Next I will search USPTO patent filings for '{patent_query}' to identify patent titles and technical claims.",
            "action": f"search_patents(\"{patent_query}\")",
            "observation": obs3
        }

        # 4. GitHub Tool Call (Focused on Tech Stack & Repositories)
        github_query = f"{domain_query} recommendation"
        obs4 = search_github(github_query)
        trace4 = {
            "step": 4,
            "thought": f"Finally I will query GitHub for '{github_query}' to identify open-source repositories and stars.",
            "action": f"search_github(\"{github_query}\")",
            "observation": obs4
        }

        # Process Observations & Format Final Answer according to Grounding Rules
        final_answer = self._synthesize_grounded_fallback_report(
            obs_news=obs1,
            obs_papers=obs2,
            obs_patents=obs3,
            obs_github=obs4,
            domain=domain_query
        )

        return {
            "status": "success",
            "user_request": user_request,
            "model": "Fallback-ReAct-Engine",
            "trace": [trace1, trace2, trace3, trace4],
            "final_answer": final_answer,
            "agentrouter_active": False
        }

    def _synthesize_grounded_fallback_report(self, obs_news: str, obs_papers: str, obs_patents: str, obs_github: str, domain: str) -> str:
        """Synthesizes strictly grounded final report with concrete entities or outputs Insufficient Data."""
        
        # Parse News Facts
        news_facts = []
        if "No results returned" not in obs_news:
            for line in obs_news.splitlines():
                if line.startswith("- Title:"):
                    news_facts.append(line.replace("- Title: ", "").strip())
        
        # Parse Paper Facts
        paper_facts = []
        if "No results returned" not in obs_papers:
            for line in obs_papers.splitlines():
                if line.startswith("- Title:"):
                    paper_facts.append(line.replace("- Title: ", "").strip())

        # Parse Patent Facts
        patent_facts = []
        if "No results returned" not in obs_patents:
            for line in obs_patents.splitlines():
                if line.startswith("- Title:"):
                    patent_facts.append(line.replace("- Title: ", "").strip())

        # Parse GitHub Facts
        github_facts = []
        if "No results returned" not in obs_github:
            for line in obs_github.splitlines():
                if line.startswith("- Repo:"):
                    github_facts.append(line.replace("- Repo: ", "").strip())

        # Build Section 1: News
        if len(news_facts) >= 2:
            sec1 = f"- Grounded Headline 1: **{news_facts[0]}** (per Web News)\n- Grounded Headline 2: **{news_facts[1]}** (per Web News)"
        elif len(news_facts) == 1:
            sec1 = f"- Grounded Headline: **{news_facts[0]}** (per Web News)"
        else:
            sec1 = "Insufficient data retrieved for this section (per Web News: 0 articles found)."

        # Build Section 2: Papers
        if len(paper_facts) >= 2:
            sec2 = f"- Publication 1: **{paper_facts[0]}** (per Semantic Scholar)\n- Publication 2: **{paper_facts[1]}** (per Semantic Scholar)"
        elif len(paper_facts) == 1:
            sec2 = f"- Publication: **{paper_facts[0]}** (per Semantic Scholar)"
        else:
            sec2 = "Insufficient data retrieved for this section (per Semantic Scholar: 0 papers found)."

        # Build Section 3: Patents
        if len(patent_facts) >= 2:
            sec3 = f"- Patent Record 1: **{patent_facts[0]}** (per PatentsView / Google Patents)\n- Patent Record 2: **{patent_facts[1]}** (per PatentsView / Google Patents)"
        elif len(patent_facts) == 1:
            sec3 = f"- Patent Record: **{patent_facts[0]}** (per PatentsView / Google Patents)"
        else:
            sec3 = "Insufficient data retrieved for this section (per PatentsView: 0 patents found)."

        # Build Section 4: GitHub
        if len(github_facts) >= 2:
            sec4 = f"- Repository 1: **{github_facts[0]}** (per GitHub API)\n- Repository 2: **{github_facts[1]}** (per GitHub API)"
        elif len(github_facts) == 1:
            sec4 = f"- Repository: **{github_facts[0]}** (per GitHub API)"
        else:
            sec4 = "Insufficient data retrieved for this section (per GitHub API: 0 repositories found)."

        return f"""# GROUNDED RESEARCH & COMPETITOR INTELLIGENCE SUMMARY: {domain.upper()}

## 1. COMPETITOR NEWS & MARKET SIGNALS
{sec1}

## 2. ACADEMIC RESEARCH & ALGORITHMIC PUBLICATIONS
{sec2}

## 3. PATENT FILINGS & INTELLECTUAL PROPERTY
{sec3}

## 4. GITHUB TECHNICAL ACTIVITY & OPEN-SOURCE REPOSITORIES
{sec4}
"""
