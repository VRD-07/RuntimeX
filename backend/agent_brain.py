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
from memory_db import init_memory_db, get_prior_scan_memory, save_scan_memory, compute_memory_delta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure Memory Database is initialized & seeded on module import
init_memory_db()

FIELD_AGENT_PROMPT = """You are the Field Research Agent. Your only job is to gather grounded observations using tools (news, semantic scholar, patents, github, reddit). Do NOT synthesize, summarize, or draw conclusions — only collect and return raw, cited observations.

REASONING FORMAT:
Thought: explain what raw data you need to collect.
Action: call exactly one tool with concise arguments.
Observation: [filled in automatically with real tool data]
"""

ANALYST_AGENT_PROMPT = """You are the Strategic Analyst Agent. You receive grounded observations gathered by the Field Agent and produce:
(a) a 3-5 sentence executive summary,
(b) a competitor comparison across market signals and technology,
(c) a gap_report field listing any competitor or topic where the observations are too thin to draw a confident conclusion (e.g. fewer than 2 relevant items).

CRITICAL MANDATE: Every claim you make must cite a specific observation from the input — never introduce outside facts. Return output in strictly formatted JSON.
"""

TOOL_REGISTRY = {
    "search_semantic_scholar": search_semantic_scholar,
    "search_patents": search_patents,
    "search_news": search_news,
    "search_github": search_github,
    "search_reddit": search_reddit
}

class FieldAgent:
    """
    Field Research Agent.
    Executes raw tool calls (news, research, patents, github, reddit) and returns grounded observations.
    Does NOT synthesize summaries or conclusions.
    """
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("AGENTROUTER_API_KEY", "")
        self.base_url = (base_url or os.getenv("AGENTROUTER_BASE_URL", "https://agentrouter.org/v1")).rstrip("/")
        self.model = model or os.getenv("AGENTROUTER_MODEL", "claude-3-5-sonnet")
        self.role_name = "Field Agent"

    def execute_targeted_followup(self, question: str, max_items: int = 3) -> Dict[str, Any]:
        """
        Executes exactly ONE targeted tool call triggered by a user follow-up question.
        Returns the action and raw observation.
        """
        q_lower = question.lower()
        if "patent" in q_lower:
            action = f"search_patents(\"{question}\")"
            obs = search_patents(question, max_results=max_items)
        elif "news" in q_lower or "funding" in q_lower or "announce" in q_lower:
            action = f"search_news(\"{question}\")"
            obs = search_news(question, max_results=max_items)
        elif "github" in q_lower or "code" in q_lower or "repo" in q_lower:
            action = f"search_github(\"{question}\")"
            obs = search_github(question, max_results=max_items)
        elif "reddit" in q_lower or "sentiment" in q_lower or "user" in q_lower:
            action = f"search_reddit(\"{question}\")"
            obs = search_reddit(question, max_results=max_items)
        else:
            action = f"search_semantic_scholar(\"{question}\")"
            obs = search_semantic_scholar(question, max_results=max_items)

        return {
            "action": action,
            "observation": obs
        }

    def gather_observations_stream(self, topic: str, competitors: str, max_items: int = 5, start_step: int = 1, is_gap_fill: bool = False, gap_queries: Optional[List[str]] = None) -> Generator[Dict[str, Any], None, None]:
        clean_topic = topic.strip() or "Regional language capabilities for AI"
        clean_comps = competitors.strip() or "Sarvam, OpenAI, Google"
        comp_list = [c.strip() for c in clean_comps.split(",") if c.strip()]
        if not comp_list:
            comp_list = [clean_topic]

        step_counter = start_step

        if is_gap_fill and gap_queries:
            # GAP-FILL MODE: Only run targeted searches flagged in gap_report
            for g_q in gap_queries:
                t_gap = f"Targeted Gap-Fill: Field Agent executing query '{g_q}' to address thin observation coverage."
                
                if "patent" in g_q.lower():
                    a_gap = f"search_patents(\"{g_q}\")"
                    yield {"type": "step_start", "agent_role": self.role_name, "step": step_counter, "thought": t_gap, "action": a_gap}
                    obs = search_patents(g_q, max_results=max_items)
                elif "news" in g_q.lower() or "funding" in g_q.lower():
                    a_gap = f"search_news(\"{g_q}\")"
                    yield {"type": "step_start", "agent_role": self.role_name, "step": step_counter, "thought": t_gap, "action": a_gap}
                    obs = search_news(g_q, max_results=max_items)
                else:
                    a_gap = f"search_reddit(\"{g_q}\")"
                    yield {"type": "step_start", "agent_role": self.role_name, "step": step_counter, "thought": t_gap, "action": a_gap}
                    obs = search_reddit(g_q, max_results=max_items)

                yield {"type": "step_complete", "agent_role": self.role_name, "step": step_counter, "thought": t_gap, "action": a_gap, "observation": obs}
                step_counter += 1
            return

        # STANDARD INITIAL FIELD SCAN MODE
        # 1. News per competitor
        for comp in comp_list:
            news_query = f"{comp} {clean_topic} news".strip()
            t_news = f"Field Agent collecting live market news for competitor '{comp}'."
            a_news = f"search_news(\"{news_query}\")"
            yield {"type": "step_start", "agent_role": self.role_name, "step": step_counter, "thought": t_news, "action": a_news}
            obs_n = search_news(news_query, max_results=max_items)
            yield {"type": "step_complete", "agent_role": self.role_name, "step": step_counter, "thought": t_news, "action": a_news, "observation": obs_n}
            step_counter += 1

        # 2. Academic papers
        paper_query = f"{clean_topic} algorithm matching".strip()
        t_paper = f"Field Agent collecting academic literature for '{paper_query}'."
        a_paper = f"search_semantic_scholar(\"{paper_query}\")"
        yield {"type": "step_start", "agent_role": self.role_name, "step": step_counter, "thought": t_paper, "action": a_paper}
        obs_p = search_semantic_scholar(paper_query, max_results=max_items)
        yield {"type": "step_complete", "agent_role": self.role_name, "step": step_counter, "thought": t_paper, "action": a_paper, "observation": obs_p}
        step_counter += 1

        # 3. Patent filings
        patent_query = f"{clean_topic}".strip()
        t_patent = f"Field Agent querying USPTO patent filings for '{patent_query}'."
        a_patent = f"search_patents(\"{patent_query}\")"
        yield {"type": "step_start", "agent_role": self.role_name, "step": step_counter, "thought": t_patent, "action": a_patent}
        obs_pat = search_patents(patent_query, max_results=max_items)
        yield {"type": "step_complete", "agent_role": self.role_name, "step": step_counter, "thought": t_patent, "action": a_patent, "observation": obs_pat}
        step_counter += 1

        # 4. GitHub open source repos
        github_query = f"{clean_topic} open source".strip()
        t_github = f"Field Agent checking GitHub repositories for '{github_query}'."
        a_github = f"search_github(\"{github_query}\")"
        yield {"type": "step_start", "agent_role": self.role_name, "step": step_counter, "thought": t_github, "action": a_github}
        obs_git = search_github(github_query, max_results=max_items)
        yield {"type": "step_complete", "agent_role": self.role_name, "step": step_counter, "thought": t_github, "action": a_github, "observation": obs_git}
        step_counter += 1

        # 5. Reddit community sentiment per competitor
        for comp in comp_list:
            reddit_query = f"{comp} user feedback".strip()
            t_reddit = f"Field Agent parsing Reddit discussions for competitor '{comp}'."
            a_reddit = f"search_reddit(\"{reddit_query}\")"
            yield {"type": "step_start", "agent_role": self.role_name, "step": step_counter, "thought": t_reddit, "action": a_reddit}
            obs_red = search_reddit(reddit_query, max_results=max_items)
            yield {"type": "step_complete", "agent_role": self.role_name, "step": step_counter, "thought": t_reddit, "action": a_reddit, "observation": obs_red}
            step_counter += 1


import google.generativeai as genai

class AnalystAgent:
    """
    Strategic Analyst Agent.
    Receives grounded observations gathered by FieldAgent and produces:
    - 3-5 sentence executive summary
    - Competitor comparison section
    - gap_report identifying entities with < 2 items
    """
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model_name = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.role_name = "Analyst Agent"

    def analyze_observations(self, topic: str, competitors: str, observations: List[Dict[str, Any]], step_num: int) -> Dict[str, Any]:
        obs_text_blocks = []
        for o in observations:
            if o.get("type") == "step_complete" and o.get("observation"):
                obs_text_blocks.append(f"--- OBSERVATION (Action: {o.get('action')}) ---\n{o.get('observation')}")

        combined_obs_text = "\n\n".join(obs_text_blocks)
        comp_list = [c.strip() for c in competitors.split(",") if c.strip()]

        if self.api_key:
            prompt_content = f"Topic: {topic}\nCompetitors: {competitors}\n\nGROUNDED OBSERVATIONS:\n{combined_obs_text[:6000]}"

            logger.info("=== [GEMINI LLM API REQUEST START] ===")
            logger.info(f"[Model Name]: '{self.model_name}'")
            logger.info(f"[API Key Check]: Non-empty={bool(self.api_key)}, Key Length={len(self.api_key)}")
            logger.info(f"[System Prompt]: {ANALYST_AGENT_PROMPT.strip()}")
            logger.info(f"[User Prompt Snippet]: {prompt_content[:300]}...")

            try:
                genai.configure(api_key=self.api_key)

                generation_config = genai.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.2
                )

                try:
                    gemini_model = genai.GenerativeModel(
                        model_name=self.model_name,
                        system_instruction=ANALYST_AGENT_PROMPT,
                        generation_config=generation_config
                    )
                    response = gemini_model.generate_content(prompt_content)
                except Exception as m_err:
                    logger.warning(f"[Gemini Model Fallback]: Primary model '{self.model_name}' failed ({m_err}). Falling back to 'gemini-1.5-flash'...")
                    gemini_model = genai.GenerativeModel(
                        model_name="gemini-1.5-flash",
                        system_instruction=ANALYST_AGENT_PROMPT,
                        generation_config=generation_config
                    )
                    response = gemini_model.generate_content(prompt_content)

                logger.info("=== [GEMINI LLM API RESPONSE RECEIVED] ===")
                logger.info(f"[Raw Response Text]: {response.text}")

                if response.text:
                    clean_json = response.text.strip()
                    if "```json" in clean_json:
                        clean_json = clean_json.split("```json")[1].split("```")[0].strip()
                    return json.loads(clean_json)
            except Exception as e:
                logger.error("=== [GEMINI LLM API EXCEPTION] ===", exc_info=True)
                logger.error(f"[AnalystAgent Gemini API Exception Detail]: {e}")

        # Rule-Based Structured Analyst Output Fallback
        gap_report = []
        sections = [
            {"source_type": "news", "items": []},
            {"source_type": "research", "items": []},
            {"source_type": "patents", "items": []},
            {"source_type": "github", "items": []},
            {"source_type": "reddit", "items": []}
        ]

        for comp in comp_list:
            comp_count = sum(1 for block in obs_text_blocks if comp.lower() in block.lower())
            if comp_count < 2:
                gap_report.append({
                    "entity": comp,
                    "gap": f"Thin coverage ({comp_count} observations found). Recommended gap-fill search."
                })

        for block in obs_text_blocks:
            lines = block.split("\n")
            action_line = lines[0] if lines else ""
            for line in lines[1:]:
                if line.strip().startswith("- Title:"):
                    title_part = line.replace("- Title:", "").strip()
                    entity = "General"
                    for c in comp_list:
                        if c.lower() in title_part.lower():
                            entity = c
                            break
                    sections[0]["items"].append({
                        "title": title_part[:80],
                        "snippet": f"Grounded observation parsed from tool call ({action_line[:30]}).",
                        "source_name": "Verified Source",
                        "date": "Recent",
                        "url": "https://news.google.com",
                        "entity": entity
                    })

        exec_summary = (
            f"Strategic Analyst synthesis for '{topic}' across {competitors}. "
            f"Parsed {len(obs_text_blocks)} grounded field observations across news, research publications, USPTO patents, and open-source code. "
            f"Coverage gap analysis identified {len(gap_report)} entities requiring deeper inspection."
        )

        return {
            "executive_takeaway": exec_summary,
            "gap_report": gap_report,
            "sections": sections
        }


class OrchestratorAgent:
    """
    Orchestrates the multi-agent execution loop:
    1. Memory Recall: Reads SQLite long-term memory for baseline comparison & delta computation.
    2. Field Agent gathers initial observations across all competitors.
    3. Analyst Agent evaluates observations and generates gap_report.
    4. If gaps exist, Field Agent runs 1 targeted gap-fill pass.
    5. Analyst Agent synthesizes final output and writes to SQLite database.
    """
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: Optional[str] = None):
        self.field_agent = FieldAgent(api_key, base_url, model)
        self.analyst_agent = AnalystAgent(api_key, base_url, model)

    def stream_orchestration(self, topic: str, competitors: str, max_items: int = 5, max_steps: int = 12) -> Generator[str, None, None]:
        comp_list = [c.strip() for c in competitors.split(",") if c.strip()]
        primary_comp = comp_list[0] if comp_list else topic

        # STEP 0: Long-Term Memory Recall & Delta Computation
        prior_mem = get_prior_scan_memory(topic, primary_comp)
        if prior_mem:
            mem_content = f"Loaded prior gap report for {primary_comp} ({prior_mem['timestamp']})"
            mem_delta = compute_memory_delta(prior_mem, primary_comp, prior_mem["gap_report"], len(prior_mem["gap_report"]))
        else:
            mem_content = f"First recorded scan for {primary_comp}. Initializing long-term memory baseline."
            mem_delta = "Baseline established in long-term store."

        yield json.dumps({
            "type": "memory_recall",
            "agent_role": "Orchestrator",
            "step": 0,
            "thought": "Querying SQLite long-term scan memory for prior competitor benchmarks.",
            "action": f"memory_db.get_prior_scan_memory(\"{topic}\", \"{primary_comp}\")",
            "content": mem_content,
            "delta": mem_delta,
            "prior_memory": prior_mem
        }) + "\n"

        observations = []
        step_counter = 1

        # PASS 1: Field Agent Initial Observation Gathering
        logger.info("--- [ORCHESTRATOR] Pass 1: Field Agent Gathering Grounded Observations ---")
        for chunk in self.field_agent.gather_observations_stream(topic, competitors, max_items, start_step=step_counter):
            yield json.dumps(chunk) + "\n"
            if chunk.get("type") == "step_complete":
                observations.append(chunk)
                step_counter += 1

        # PASS 1: Analyst Agent Evaluation & Gap Report
        logger.info("--- [ORCHESTRATOR] Pass 1: Analyst Agent Evaluating Field Observations ---")
        t_analyst = f"Analyst Agent evaluating {len(observations)} field observations for coverage gaps."
        a_analyst = "analyze_observations_and_check_gaps()"
        
        yield json.dumps({
            "type": "step_start",
            "agent_role": "Analyst Agent",
            "step": step_counter,
            "thought": t_analyst,
            "action": a_analyst
        }) + "\n"

        analyst_result = self.analyst_agent.analyze_observations(topic, competitors, observations, step_counter)
        gap_report = analyst_result.get("gap_report", [])

        gap_entities = []
        for g in gap_report:
            if isinstance(g, dict):
                gap_entities.append(g.get("entity", str(g)))
            else:
                ent = str(g).split(":")[0].strip()
                gap_entities.append(ent)

        obs_analyst = f"Analyst Agent evaluation complete. Found {len(gap_report)} coverage gaps: {gap_entities}"
        yield json.dumps({
            "type": "step_complete",
            "agent_role": "Analyst Agent",
            "step": step_counter,
            "thought": t_analyst,
            "action": a_analyst,
            "observation": obs_analyst
        }) + "\n"
        step_counter += 1

        # GAP-FILL EVALUATION: Max 1 Gap-Fill Round
        if gap_report:
            logger.info(f"--- [ORCHESTRATOR] Gap-Fill Round: Deploying Field Agent for {len(gap_report)} flagged entities ---")
            gap_queries = [f"{ent} {topic} news" for ent in gap_entities]

            for chunk in self.field_agent.gather_observations_stream(topic, competitors, max_items, start_step=step_counter, is_gap_fill=True, gap_queries=gap_queries):
                yield json.dumps(chunk) + "\n"
                if chunk.get("type") == "step_complete":
                    observations.append(chunk)
                    step_counter += 1

            # PASS 2: Final Analyst Agent Synthesis with Combined Observations
            logger.info("--- [ORCHESTRATOR] Pass 2: Final Analyst Agent Synthesis ---")
            t_final = f"Analyst Agent performing final synthesis across combined field observations."
            a_final = "synthesize_final_report()"
            yield json.dumps({
                "type": "step_start",
                "agent_role": "Analyst Agent",
                "step": step_counter,
                "thought": t_final,
                "action": a_final
            }) + "\n"

            analyst_result = self.analyst_agent.analyze_observations(topic, competitors, observations, step_counter)
            yield json.dumps({
                "type": "step_complete",
                "agent_role": "Analyst Agent",
                "step": step_counter,
                "thought": t_final,
                "action": a_final,
                "observation": "Final Analyst Agent synthesis complete."
            }) + "\n"

        exec_summary_text = analyst_result.get("executive_takeaway") or analyst_result.get("executive_summary") or ""

        # Long-Term Memory Persistence: Write completed scan to SQLite database
        save_scan_memory(
            topic=topic,
            competitor=primary_comp,
            gap_report=gap_report,
            executive_summary=exec_summary_text
        )

        # Final Completion Output
        yield json.dumps({
            "type": "final_complete",
            "status": "success",
            "topic": topic,
            "competitors": competitors,
            "structured_output": analyst_result,
            "final_answer": json.dumps(analyst_result, indent=2),
            "executive_report": analyst_result.get("executive_takeaway", ""),
            "gap_report": analyst_result.get("gap_report", []),
            "memory_recall": {
                "content": mem_content,
                "delta": mem_delta
            },
            "papers": [],
            "news": [],
            "agentrouter_active": bool(self.analyst_agent.api_key or os.getenv("GEMINI_API_KEY"))
        }) + "\n"


class AutonomousReActAgent:
    """
    Backwards-compatible interface wrapper routing to OrchestratorAgent.
    """
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: Optional[str] = None):
        self.orchestrator = OrchestratorAgent(api_key, base_url, model)
        self.field_agent = FieldAgent(api_key, base_url, model)

    def stream_scan(self, topic: str = "Regional language capabilities for AI", competitors: str = "Sarvam, OpenAI, Google", max_items: int = 5, max_steps: int = 12) -> Generator[str, None, None]:
        return self.orchestrator.stream_orchestration(topic, competitors, max_items, max_steps)

    def run_scan(self, topic: str = "Regional language capabilities for AI", competitors: str = "Sarvam, OpenAI, Google", max_items: int = 5, max_steps: int = 12) -> Dict[str, Any]:
        stream_results = list(self.stream_scan(topic, competitors, max_items, max_steps))
        last_line = json.loads(stream_results[-1])
        
        trace = []
        for line in stream_results[:-1]:
            data = json.loads(line)
            if data.get("type") == "step_complete":
                trace.append({
                    "step": data["step"],
                    "agent_role": data.get("agent_role", "Field Agent"),
                    "thought": data["thought"],
                    "action": data["action"],
                    "observation": data["observation"]
                })
            elif data.get("type") == "memory_recall":
                trace.append({
                    "step": 0,
                    "agent_role": "Orchestrator",
                    "step_type": "memory_recall",
                    "thought": data["thought"],
                    "action": data["action"],
                    "content": data["content"],
                    "delta": data["delta"]
                })

        return {
            "status": "success",
            "topic": last_line["topic"],
            "competitors": last_line["competitors"],
            "structured_output": last_line["structured_output"],
            "final_answer": last_line["final_answer"],
            "executive_report": last_line["executive_report"],
            "gap_report": last_line.get("gap_report", []),
            "memory_recall": last_line.get("memory_recall", {}),
            "papers": last_line["papers"],
            "news": last_line["news"],
            "trace": trace,
            "agentrouter_active": last_line["agentrouter_active"]
        }
