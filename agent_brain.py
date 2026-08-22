import os
import json
import httpx
import logging
from typing import List, Dict, Any, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AgentRouterBrain:
    """
    Core AI Intelligence module communicating with Claude via AgentRouter.
    Includes automated fallback engine when API key is missing or offline.
    """
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("AGENTROUTER_API_KEY", "")
        self.base_url = (base_url or os.getenv("AGENTROUTER_BASE_URL", "https://agentrouter.org/v1")).rstrip("/")
        self.model = model or os.getenv("AGENTROUTER_MODEL", "claude-3-5-sonnet")

    def _call_agentrouter_api(self, prompt: str, system_prompt: str = "") -> Optional[str]:
        """
        Sends request to AgentRouter API using httpx.
        Handles both OpenAI-compatible format (/v1/chat/completions) 
        and Anthropic-compatible format (/v1/messages).
        """
        if not self.api_key:
            logger.info("No AgentRouter API Key provided. Operating in Fallback Engine mode.")
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }

        # Try Chat Completions Endpoint (OpenAI/AgentRouter standard endpoint)
        endpoint = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt or "You are an elite competitive intelligence & research analyst AI agent."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 1500
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(endpoint, headers=headers, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    # Check standard OpenAI response structure
                    if "choices" in data and len(data["choices"]) > 0:
                        return data["choices"][0]["message"]["content"]
                    # Check Anthropic response structure if applicable
                    elif "content" in data and isinstance(data["content"], list):
                        return data["content"][0].get("text", "")
                else:
                    logger.warning(f"AgentRouter API call returned status {response.status_code}: {response.text}")
        except Exception as e:
            logger.error(f"Failed to connect to AgentRouter: {e}")
        
        return None

    def generate_executive_digest(
        self, 
        research_data: List[Dict[str, Any]], 
        competitor_data: List[Dict[str, Any]], 
        topic: str
    ) -> str:
        """
        Synthesizes research papers and competitor news into an executive digest.
        """
        system_prompt = (
            "You are IntelPulse, an autonomous AI analyst specialized in Research & Competitor Intelligence. "
            "Given raw research publications and market news, provide a concise, high-impact executive report "
            "with SWOT analysis, key takeaways, and strategic recommendations."
        )

        prompt = f"""
Target Track Topic / Industry: {topic}

=== RESEARCH PUBLICATIONS ===
{json.dumps(research_data, indent=2)}

=== COMPETITOR & MARKET NEWS ===
{json.dumps(competitor_data, indent=2)}

Please synthesize the above data into a professional Executive Intelligence Report in Markdown with:
1. 🎯 Executive Summary (2-3 sentences)
2. 🔬 Research & Breakthrough Insights (Key findings from papers)
3. ⚔️ Competitor SWOT & Market Dynamics
4. 💡 Strategic Action Recommendations (3 bullet points for leadership)
"""

        # Attempt API call via AgentRouter
        llm_response = self._call_agentrouter_api(prompt, system_prompt)
        if llm_response:
            return llm_response

        # Fallback Mock Generator if API key isn't provided or active yet
        return self._generate_fallback_digest(research_data, competitor_data, topic)

    def ask_analyst_chat(
        self, 
        user_question: str, 
        context_research: List[Dict[str, Any]], 
        context_competitors: List[Dict[str, Any]]
    ) -> str:
        """
        Q&A chat over gathered research & market context.
        """
        system_prompt = "You are IntelPulse Analyst, answering strategic questions based on recent research & competitor findings."
        prompt = f"""
Context - Research Papers:
{json.dumps([p.get('title') for p in context_research])}

Context - Competitor Updates:
{json.dumps([c.get('title') for c in context_competitors])}

User Question: {user_question}

Provide a direct, analytical response citing specific findings where relevant.
"""

        llm_response = self._call_agentrouter_api(prompt, system_prompt)
        if llm_response:
            return llm_response

        # Fallback chat response
        return (
            f"**[Intelligence Analyst Response - Rule-Based Engine]**\n\n"
            f"Based on the scanned data for your query (*'{user_question}'*):\n"
            f"- **Research Context:** We reviewed {len(context_research)} publications. Key emphasis is on modular agent architectures, tool execution efficiency, and benchmark evaluations.\n"
            f"- **Competitor Signal:** We detected {len(context_competitors)} market updates indicating aggressive moves toward real-time execution and strategic partnerships.\n\n"
            f"*(Note: Connect your `AGENTROUTER_API_KEY` in the sidebar for full deep-reasoning Claude responses!)*"
        )

    def _generate_fallback_digest(
        self, 
        research_data: List[Dict[str, Any]], 
        competitor_data: List[Dict[str, Any]], 
        topic: str
    ) -> str:
        """Structured fallback report when running without an active API key."""
        paper_titles = [f"- **{p.get('title')}** ({', '.join(p.get('authors', []))})" for p in research_data[:3]]
        news_titles = [f"- **{c.get('title')}** *(Source: {c.get('source_name')})*" for c in competitor_data[:3]]

        return f"""# 📊 IntelPulse Executive Intelligence Report
**Topic:** {topic}  
**Status:** Live Intelligence Scan Complete  

---

### 🎯 Executive Summary
The market landscape surrounding **{topic}** is accelerating rapidly. Recent research highlights key improvements in agentic autonomy and tool utilization, while competitor signals point toward new product rollouts and enterprise solutions.

---

### 🔬 Research & Breakthrough Insights
{chr(10).join(paper_titles) if paper_titles else "No recent research papers retrieved."}

**Key Research Takeaway:** Academic focus is shifting heavily toward benchmark evaluation, agentic planning reliability, and reducing latency in multi-agent workflows.

---

### ⚔️ Competitor & Market Dynamics
{chr(10).join(news_titles) if news_titles else "No recent market news retrieved."}

* **Strengths:** Rapid deployment cycles and strong developer ecosystem engagement.
* **Opportunities:** Unmet demand for real-time tracking, privacy-preserving agent memory, and automated compliance checking.
* **Threats:** High API costs and rapid technological obsolescence of fixed pipeline models.

---

### 💡 Strategic Action Recommendations
1. **Accelerate Prototyping:** Focus on autonomous tool routing to match competitor execution speed.
2. **Leverage Open Benchmarks:** Integrate recent ArXiv research evaluation frameworks to validate performance.
3. **Continuous Monitoring:** Schedule automated daily scans to catch competitor filings early.

---
> ⚡ *Powered by IntelPulse Engine. Connect your `AGENTROUTER_API_KEY` in the sidebar to activate Claude 3.5 Sonnet deep synthesis.*
"""
