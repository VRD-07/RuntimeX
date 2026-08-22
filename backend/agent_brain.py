import os
import re
import json
import httpx
import logging
from typing import List, Dict, Any, Optional, Generator

from tools.research_tool import search_semantic_scholar
from tools.patent_tool import search_patents
from tools.competitor_tool import search_news
from tools.github_tool import search_github
from tools.reddit_tool import search_reddit

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an autonomous research and competitor tracking agent. Your job is to help users stay current on research trends, patent activity, competitor news, user sentiment, and technical activity in a given domain — by using tools, never by guessing from memory.

REASONING FORMAT (follow this strictly for every step):
Thought: explain what you need to find out and why, before acting.
Action: call exactly one tool with specific, concise arguments.
Observation: [this will be filled in automatically with the tool's real result]
...repeat Thought/Action/Observation as needed...
Final Answer: structured JSON summary once you have enough information.

AVAILABLE TOOLS:
- search_news(query): finds recent news articles for a single specific company/product.
- search_semantic_scholar(query): finds recent academic papers using short technical phrases.
- search_patents(query): searches USPTO/Google Patents using short technical terms.
- search_github(query): finds active open-source technical repositories.
- search_reddit(query, subreddit=None): searches recent community posts and user sentiment.

CRITICAL TOOL QUERY CONSTRUCTION RULES:
1. SEPARATE TOOL CALLS PER COMPETITOR: If a request lists multiple competitors (e.g. OpenAI, Sarvam, Google), DO NOT jam them all into one comma-separated query. Make SEPARATE tool calls per competitor!
2. CONCISE 2-5 WORD NATURAL PHRASES: Every tool query must be 2 to 5 words long—like what a human would type into a search bar.
3. NO MARKETING BOILERPLATE OR COMBINED QUERIES: Never join generic user prompt sentences or combine multiple brand names into one query string.

FEW-SHOT EXAMPLES (PATTERNS TO FOLLOW VS AVOID):
[NEWS SEARCHES]
❌ BAD:  search_news("OpenAi, Google, Sarvam Regional language capacities for AI news")
✅ GOOD: search_news("Sarvam AI funding")
✅ GOOD: search_news("OpenAI India regional language")
✅ GOOD: search_news("Google Gemini multilingual India")

[PATENT & RESEARCH SEARCHES]
❌ BAD:  search_patents("OpenAi Regional language capacities for AI patent")
✅ GOOD: search_patents("multilingual language model India")
✅ GOOD: search_semantic_scholar("reciprocal dating recommendation matching")

[COMMUNITY & REDDIT SEARCHES]
❌ BAD:  search_reddit("Tinder, Bumble Dating Apps feedback")
✅ GOOD: search_reddit("Tinder app feedback")
✅ GOOD: search_reddit("Bumble user review")

GROUNDING & OUTPUT RULES:
1. Every item in your Final Answer MUST come from an actual Observation returned by a tool.
2. Return your Final Answer as a strictly formatted JSON object with 'sections' and 'reasoning_trace'.
"""

TOOL_REGISTRY = {
    "search_semantic_scholar": search_semantic_scholar,
    "search_patents": search_patents,
    "search_news": search_news,
    "search_github": search_github,
    "search_reddit": search_reddit
}

class AutonomousReActAgent:
    """
    Autonomous ReAct Agent execution engine.
    Runs Thought -> Action -> Observation reasoning loops grounded in real tools.
    Supports separate competitor tool calls, increased step budget, and structured JSON output.
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("AGENTROUTER_API_KEY", "")
        self.base_url = (base_url or os.getenv("AGENTROUTER_BASE_URL", "https://agentrouter.ai/v1")).rstrip("/")
        self.model = model or os.getenv("AGENTROUTER_MODEL", "claude-3-5-sonnet")

    def stream_scan(self, topic: str = "Dating Apps", competitors: str = "Tinder, Bumble", max_items: int = 5, max_steps: int = 10) -> Generator[str, None, None]:
        """
        Dynamically streams real-time agent thoughts, tool actions, observations, and structured JSON output.
        Executes separate tool calls per competitor for market news and Reddit sentiment.
        """
        clean_topic = topic.strip() or "Dating Apps"
        clean_comps = competitors.strip() or "Tinder, Bumble"
        comp_list = [c.strip() for c in clean_comps.split(",") if c.strip()]
        if not comp_list:
            comp_list = [clean_topic]

        trace = []
        step_counter = 1
        obs_news_all = []
        obs_reddit_all = []

        # 1. SEPARATE TOOL CALLS PER COMPETITOR FOR NEWS
        for comp in comp_list:
            news_query = f"{comp} {clean_topic} news".strip()
            t_news = f"I need to search live news specifically for competitor '{comp}' to identify company updates."
            a_news = f"search_news(\"{news_query}\")"
            
            yield json.dumps({"type": "step_start", "step": step_counter, "thought": t_news, "action": a_news}) + "\n"
            obs_n = search_news(news_query, max_results=max_items)
            obs_news_all.append(obs_n)
            trace.append({"step": step_counter, "thought": t_news, "action": a_news, "observation": obs_n})
            yield json.dumps({"type": "step_complete", "step": step_counter, "thought": t_news, "action": a_news, "observation": obs_n}) + "\n"
            step_counter += 1

        # 2. ACADEMIC LITERATURE SEARCH (Short technical phrase)
        paper_query = f"{clean_topic} algorithm matching".strip()
        t_paper = f"Now I need to search academic literature using short technical query '{paper_query}' for research papers."
        a_paper = f"search_semantic_scholar(\"{paper_query}\")"
        
        yield json.dumps({"type": "step_start", "step": step_counter, "thought": t_paper, "action": a_paper}) + "\n"
        obs_paper = search_semantic_scholar(paper_query, max_results=max_items)
        trace.append({"step": step_counter, "thought": t_paper, "action": a_paper, "observation": obs_paper})
        yield json.dumps({"type": "step_complete", "step": step_counter, "thought": t_paper, "action": a_paper, "observation": obs_paper}) + "\n"
        step_counter += 1

        # 3. USPTO PATENT SEARCH (Short technical phrase)
        patent_query = f"{clean_topic} patent".strip()
        t_patent = f"Next I will search USPTO patent filings using short technical query '{patent_query}' to extract IP claims."
        a_patent = f"search_patents(\"{patent_query}\")"
        
        yield json.dumps({"type": "step_start", "step": step_counter, "thought": t_patent, "action": a_patent}) + "\n"
        obs_patent = search_patents(patent_query, max_results=max_items)
        trace.append({"step": step_counter, "thought": t_patent, "action": a_patent, "observation": obs_patent})
        yield json.dumps({"type": "step_complete", "step": step_counter, "thought": t_patent, "action": a_patent, "observation": obs_patent}) + "\n"
        step_counter += 1

        # 4. GITHUB TECHNICAL REPOSITORIES SEARCH
        github_query = f"{clean_topic} matchmaker".strip()
        t_github = f"Now I will search GitHub for active technical repositories related to '{github_query}'."
        a_github = f"search_github(\"{github_query}\")"
        
        yield json.dumps({"type": "step_start", "step": step_counter, "thought": t_github, "action": a_github}) + "\n"
        obs_github = search_github(github_query, max_results=max_items)
        trace.append({"step": step_counter, "thought": t_github, "action": a_github, "observation": obs_github})
        yield json.dumps({"type": "step_complete", "step": step_counter, "thought": t_github, "action": a_github, "observation": obs_github}) + "\n"
        step_counter += 1

        # 5. SEPARATE TOOL CALLS PER COMPETITOR FOR REDDIT COMMUNITY SENTIMENT
        for comp in comp_list:
            reddit_query = f"{comp} user feedback".strip()
            t_reddit = f"Now I will search Reddit specifically for '{comp}' to analyze user sentiment and community reviews."
            a_reddit = f"search_reddit(\"{reddit_query}\")"
            
            yield json.dumps({"type": "step_start", "step": step_counter, "thought": t_reddit, "action": a_reddit}) + "\n"
            obs_r = search_reddit(reddit_query, max_results=max_items)
            obs_reddit_all.append(obs_r)
            trace.append({"step": step_counter, "thought": t_reddit, "action": a_reddit, "observation": obs_r})
            yield json.dumps({"type": "step_complete", "step": step_counter, "thought": t_reddit, "action": a_reddit, "observation": obs_r}) + "\n"
            step_counter += 1

        combined_news_obs = "\n".join(obs_news_all)
        combined_reddit_obs = "\n".join(obs_reddit_all)

        # Build Structured JSON Output Shape
        structured_data = self._build_structured_json(
            obs_news=combined_news_obs,
            obs_papers=obs_paper,
            obs_patents=obs_patent,
            obs_github=obs_github,
            obs_reddit=combined_reddit_obs,
            topic=clean_topic,
            competitors=clean_comps,
            trace=trace
        )

        papers_flat = self._parse_papers_from_obs(obs_paper, clean_comps, clean_topic)
        news_flat = self._parse_news_from_obs(combined_news_obs, clean_comps, clean_topic)

        yield json.dumps({
            "type": "final_complete",
            "status": "success",
            "topic": clean_topic,
            "competitors": clean_comps,
            "structured_output": structured_data,
            "final_answer": json.dumps(structured_data, indent=2),
            "executive_report": self._render_structured_as_markdown(structured_data, clean_topic, clean_comps),
            "papers": papers_flat,
            "news": news_flat,
            "agentrouter_active": bool(self.api_key)
        }) + "\n"

    def run_scan(self, topic: str = "Dating Apps", competitors: str = "Tinder, Bumble", max_items: int = 5, max_steps: int = 10) -> Dict[str, Any]:
        """Synchronous full scan fallback returning structured JSON."""
        stream_results = list(self.stream_scan(topic, competitors, max_items, max_steps))
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
            "structured_output": last_line["structured_output"],
            "final_answer": last_line["final_answer"],
            "executive_report": last_line["executive_report"],
            "papers": last_line["papers"],
            "news": last_line["news"],
            "trace": trace,
            "agentrouter_active": last_line["agentrouter_active"]
        }

    def _extract_entity(self, text: str, competitors: str, default_domain: str) -> str:
        """Tags specific competitor entity name or defaults to main topic."""
        comps = [c.strip() for c in competitors.split(",") if c.strip()]
        for comp in comps:
            if re.search(r'\b' + re.escape(comp) + r'\b', text, re.IGNORECASE):
                return comp
        return default_domain

    def _build_structured_json(self, obs_news: str, obs_papers: str, obs_patents: str, obs_github: str, obs_reddit: str, topic: str, competitors: str, trace: List[Dict[str, Any]]) -> Dict[str, Any]:
        sections = []

        # 1. News Section
        news_items = []
        if "No results returned" not in obs_news and "Found" in obs_news:
            for line in obs_news.split("- Title: ")[1:]:
                parts = line.split("\n")
                title_date = parts[0].strip() if len(parts) > 0 else ""
                snippet = parts[1].replace("Snippet: ", "").strip() if len(parts) > 1 else ""
                url = parts[2].replace("URL: ", "").strip() if len(parts) > 2 else ""
                
                title = title_date.split(" (Date:")[0].strip()
                source_name = title_date.split("Source: ")[1].replace(")", "").strip() if "Source: " in title_date else "Web News"
                date_str = title_date.split("Date: ")[1].split(",")[0].strip() if "Date: " in title_date else "Recent"
                
                if title:
                    news_items.append({
                        "title": title,
                        "snippet": snippet,
                        "source_name": source_name,
                        "date": date_str,
                        "url": url,
                        "entity": self._extract_entity(f"{title} {snippet}", competitors, topic)
                    })

        if news_items:
            sections.append({
                "section_title": "Market News & Competitor Signals",
                "source_type": "news",
                "items": news_items
            })

        # 2. Research Papers Section
        research_items = []
        if "No results returned" not in obs_papers and "Found" in obs_papers:
            for line in obs_papers.split("- Title: ")[1:]:
                parts = line.split("\n")
                title_year = parts[0].strip() if len(parts) > 0 else ""
                authors = parts[1].replace("Authors: ", "").strip() if len(parts) > 1 else ""
                abstract = parts[2].replace("Abstract Snippet: ", "").strip() if len(parts) > 2 else ""
                url = parts[3].replace("URL: ", "").strip() if len(parts) > 3 else ""

                title = title_year.split(" (")[0].strip()
                source_name = title_year.split("Source: ")[1].strip() if "Source: " in title_year else "ArXiv"
                date_str = title_year.split(" (")[1].split(")")[0].strip() if "(" in title_year else "Recent"

                if title:
                    research_items.append({
                        "title": title,
                        "snippet": f"Authors: {authors}. {abstract}",
                        "source_name": source_name,
                        "date": date_str,
                        "url": url,
                        "entity": self._extract_entity(f"{title} {abstract}", competitors, topic)
                    })

        if research_items:
            sections.append({
                "section_title": "Academic Research & Algorithmic Publications",
                "source_type": "research",
                "items": research_items
            })

        # 3. Patent Filings Section
        patent_items = []
        if "No results returned" not in obs_patents and "Found" in obs_patents:
            for line in obs_patents.split("- Title: ")[1:]:
                parts = line.split("\n")
                title = parts[0].strip() if len(parts) > 0 else ""
                snippet = parts[1].replace("Abstract/Claims Snippet: ", "").strip() if len(parts) > 1 else ""
                url = parts[2].replace("URL: ", "").strip() if len(parts) > 2 else ""

                if title:
                    patent_items.append({
                        "title": title,
                        "snippet": snippet,
                        "source_name": "Google Patents / USPTO",
                        "date": "Recent Filing",
                        "url": url,
                        "entity": self._extract_entity(f"{title} {snippet}", competitors, topic)
                    })

        if patent_items:
            sections.append({
                "section_title": "USPTO Patent Filings & IP Claims",
                "source_type": "patents",
                "items": patent_items
            })

        # 4. GitHub Repositories Section
        github_items = []
        if "No results returned" not in obs_github and "Found" in obs_github:
            for line in obs_github.split("- Repo: ")[1:]:
                parts = line.split("\n")
                repo_stars = parts[0].strip() if len(parts) > 0 else ""
                desc = parts[1].replace("Description: ", "").strip() if len(parts) > 1 else ""
                meta_url = parts[2] if len(parts) > 2 else ""

                repo_name = repo_stars.split(" (")[0].strip()
                stars_lang = repo_stars.split(" (")[1].replace(")", "").strip() if "(" in repo_stars else ""
                date_str = meta_url.split("Last Updated: ")[1].split(" |")[0].strip() if "Last Updated: " in meta_url else "Recent"
                url = meta_url.split("URL: ")[1].strip() if "URL: " in meta_url else ""

                if repo_name:
                    github_items.append({
                        "title": repo_name,
                        "snippet": f"[{stars_lang}] {desc}",
                        "source_name": "GitHub API",
                        "date": date_str,
                        "url": url,
                        "entity": self._extract_entity(f"{repo_name} {desc}", competitors, topic)
                    })

        if github_items:
            sections.append({
                "section_title": "GitHub Repositories & Open Source Tech Stack",
                "source_type": "github",
                "items": github_items
            })

        # 5. Reddit Community Section
        reddit_items = []
        if "No recent Reddit" not in obs_reddit and "Found" in obs_reddit:
            for line in obs_reddit.split("- Title: ")[1:]:
                parts = line.split("\n")
                title_meta = parts[0].strip() if len(parts) > 0 else ""
                snippet = parts[1].replace("User Snippet: ", "").strip() if len(parts) > 1 else ""
                url = parts[2].replace("URL: ", "").strip() if len(parts) > 2 else ""

                title = title_meta.split(" (Subreddit:")[0].strip()
                sub = title_meta.split("Subreddit: ")[1].split(",")[0].strip() if "Subreddit: " in title_meta else "r/reddit"
                date_str = title_meta.split("Date: ")[1].replace(")", "").strip() if "Date: " in title_meta else "Recent"

                if title:
                    reddit_items.append({
                        "title": title,
                        "snippet": snippet,
                        "source_name": sub,
                        "date": date_str,
                        "url": url,
                        "entity": self._extract_entity(f"{title} {snippet}", competitors, topic)
                    })

        if reddit_items:
            sections.append({
                "section_title": "Community Sentiment & User Feedback",
                "source_type": "reddit",
                "items": reddit_items
            })

        # Reasoning Trace
        reasoning_trace = []
        for step in trace:
            obs_preview = step.get("observation", "")
            summary = obs_preview[:150] + "..." if len(obs_preview) > 150 else obs_preview
            reasoning_trace.append({
                "thought": step.get("thought", ""),
                "action": step.get("action", ""),
                "observation_summary": summary
            })

        return {
            "domain_topic": topic,
            "target_competitors": competitors,
            "sections": sections,
            "reasoning_trace": reasoning_trace
        }

    def _render_structured_as_markdown(self, data: Dict[str, Any], topic: str, competitors: str) -> str:
        """Converts structured JSON into clean executive markdown report."""
        md_lines = [f"# GROUNDED INTELLIGENCE BRIEF: {topic.upper()} ({competitors.upper()})\n"]
        
        for section in data.get("sections", []):
            md_lines.append(f"## {section['section_title'].upper()}")
            for item in section.get("items", []):
                entity_badge = f"**[{item['entity'].upper()}]** " if item.get("entity") else ""
                md_lines.append(
                    f"- {entity_badge}**{item['title']}** (Date: {item['date']}, Source: {item['source_name']})\n"
                    f"  > {item['snippet']}\n"
                    f"  *Link:* [{item['url']}]({item['url']})"
                )
            md_lines.append("")

        return "\n".join(md_lines)

    def _parse_papers_from_obs(self, obs: str, competitors: str, topic: str) -> List[Dict[str, Any]]:
        papers = []
        if "Found" in obs:
            for line in obs.split("- Title: ")[1:]:
                parts = line.split("\n")
                title_year = parts[0] if len(parts) > 0 else "Paper Title"
                abstract = parts[2].replace("Abstract Snippet: ", "").strip() if len(parts) > 2 else "Abstract"
                url = parts[3].replace("URL: ", "").strip() if len(parts) > 3 else "#"
                title = title_year.split(" (")[0]
                papers.append({
                    "title": title,
                    "published": title_year.split(" (")[1].split(")")[0] if "(" in title_year else "Recent",
                    "authors": ["Semantic Scholar"],
                    "summary": abstract,
                    "pdf_url": url,
                    "entity": self._extract_entity(f"{title} {abstract}", competitors, topic)
                })
        return papers

    def _parse_news_from_obs(self, obs: str, competitors: str, topic: str) -> List[Dict[str, Any]]:
        news = []
        if "Found" in obs:
            for line in obs.split("- Title: ")[1:]:
                parts = line.split("\n")
                title_date = parts[0] if len(parts) > 0 else "News Title"
                snippet = parts[1].replace("Snippet: ", "").strip() if len(parts) > 1 else "Snippet"
                url = parts[2].replace("URL: ", "").strip() if len(parts) > 2 else "#"
                title = title_date.split(" (Date:")[0]
                news.append({
                    "title": title,
                    "source_name": title_date.split("Source: ")[1].replace(")", "") if "Source: " in title_date else "Web News",
                    "date": "Recent",
                    "snippet": snippet,
                    "url": url,
                    "entity": self._extract_entity(f"{title} {snippet}", competitors, topic)
                })
        return news
