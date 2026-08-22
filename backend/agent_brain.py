import os
import json
import logging
from typing import List, Dict, Any, Optional, Generator

from tools.research_tool import search_semantic_scholar
from tools.patent_tool import search_patents
from tools.competitor_tool import search_news
from tools.github_tool import search_github
from tools.reddit_tool import search_reddit
from memory_db import init_memory_db, get_prior_scan_memory, save_scan_memory, compute_memory_delta

logger = logging.getLogger(__name__)

# Ensure Memory Database is initialized & seeded on module import
init_memory_db()

# The Google SDK is an optional import: if it is unavailable the service still runs and
# degrades to the deterministic rule-based analyst instead of failing to start.
try:
    from google import genai
    from google.genai import types as genai_types
    GENAI_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on deployment environment
    genai = None
    genai_types = None
    GENAI_AVAILABLE = False
    logger.warning(
        "google-genai is not installed. LLM synthesis is disabled; "
        "the rule-based analyst fallback will be used. Install it with "
        "'pip install google-genai' to enable Gemini synthesis."
    )

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
SUPPORTED_GEMINI_MODELS = {
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
}
# Section order also defines the source_type buckets exposed to the frontend
SECTION_ORDER = ["news", "research", "patents", "github", "reddit"]
# A competitor with fewer than this many grounded items is reported as a coverage gap
GAP_THRESHOLD = 2


def resolve_model(requested: Optional[str]) -> str:
    """
    Resolves a requested model name to a valid Gemini model id.

    The backend runs on Gemini. A non-Gemini name (e.g. a stale 'claude-*' value from a cached
    frontend build) is logged and replaced with the default rather than sent upstream to fail.
    """
    env_default = os.getenv("GEMINI_MODEL", "").strip() or DEFAULT_GEMINI_MODEL

    if not requested or not requested.strip():
        return env_default

    name = requested.strip()
    if name in SUPPORTED_GEMINI_MODELS or name.startswith("gemini-"):
        return name

    logger.warning(
        f"[Model Resolution]: Requested model '{name}' is not a Gemini model. "
        f"This backend serves Gemini only — using '{env_default}' instead."
    )
    return env_default


def llm_available() -> bool:
    """True when the Gemini SDK is importable and an API key is configured."""
    return GENAI_AVAILABLE and bool(os.getenv("GEMINI_API_KEY", "").strip())


def call_gemini(prompt_content: str, system_instruction: str, model_name: str,
                json_mode: bool = False, temperature: float = 0.2) -> Optional[str]:
    """
    Single entry point for Gemini calls.

    Retries once on the configured default model if the requested id fails, and returns None
    when the SDK, the key, or every attempt is unavailable so callers can fall back cleanly.
    """
    if not llm_available():
        return None

    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", "").strip())
        config_kwargs: Dict[str, Any] = {
            "system_instruction": system_instruction,
            "temperature": temperature,
            # This backend runs its own tool loop and never passes tools to
            # Gemini, so the SDK's automatic function calling has nothing to do.
            # Disabling it removes the advisory the SDK logs on every call.
            "automatic_function_calling": genai_types.AutomaticFunctionCallingConfig(disable=True),
        }
        if json_mode:
            config_kwargs["response_mime_type"] = "application/json"
        config = genai_types.GenerateContentConfig(**config_kwargs)
    except Exception as e:
        logger.error(f"[Gemini] Client configuration failed: {e}")
        return None

    attempts = [model_name]
    if model_name != DEFAULT_GEMINI_MODEL:
        attempts.append(DEFAULT_GEMINI_MODEL)

    last_error: Optional[Exception] = None
    for attempt_model in attempts:
        try:
            response = client.models.generate_content(
                model=attempt_model,
                contents=prompt_content,
                config=config,
            )
            text = (response.text or "").strip()
            if text:
                logger.info(f"[Gemini] Call succeeded with model '{attempt_model}' ({len(text)} chars).")
                return text
            logger.warning(f"[Gemini] Model '{attempt_model}' returned an empty response.")
        except Exception as e:
            last_error = e
            logger.warning(f"[Gemini] Model '{attempt_model}' failed: {e}")

    logger.error(f"[Gemini] All attempts failed. Last error: {last_error}")
    return None


FIELD_AGENT_PROMPT = """You are the Field Research Agent. Your only job is to gather grounded observations using tools (news, semantic scholar, patents, github, reddit). Do NOT synthesize, summarize, or draw conclusions — only collect and return raw, cited observations.

REASONING FORMAT:
Thought: explain what raw data you need to collect.
Action: call exactly one tool with concise arguments.
Observation: [filled in automatically with real tool data]
"""

ANALYST_AGENT_PROMPT = """You are the Strategic Analyst Agent. You receive grounded observations gathered by the Field Agent, plus a precomputed coverage gap report.

Produce a JSON object with exactly one key:
  "executive_takeaway": a 3-5 sentence executive summary covering the competitive picture and, where the observations support it, a comparison across market signals and technology.

CRITICAL MANDATE: Every claim must trace back to a specific observation in the input. Never introduce outside facts, and never invent titles, sources, dates, or URLs. If the observations are too thin to support a claim, say so plainly instead of speculating.

Return strictly formatted JSON with no markdown fences.
"""

TOOL_REGISTRY = {
    "search_semantic_scholar": search_semantic_scholar,
    "search_patents": search_patents,
    "search_news": search_news,
    "search_github": search_github,
    "search_reddit": search_reddit
}


def infer_entity(item: Dict[str, Any], comp_list: List[str]) -> str:
    """Attributes an item to a competitor by name match on its title or snippet."""
    haystack = f"{item.get('title', '')} {item.get('snippet', '')}".lower()
    for comp in comp_list:
        if comp and comp.lower() in haystack:
            return comp
    return "General"


def build_sections(observations: List[Dict[str, Any]], comp_list: List[str]) -> List[Dict[str, Any]]:
    """
    Assembles the findings list from real tool output.

    This is deliberately deterministic: titles, sources, dates and URLs are carried through
    from the upstream APIs so nothing displayed to the user is model-generated. Items repeated
    across the initial and gap-fill passes are de-duplicated on (source_type, url, title).
    """
    buckets: Dict[str, List[Dict[str, Any]]] = {s: [] for s in SECTION_ORDER}
    seen = set()

    for obs in observations:
        source_type = obs.get("source_type")
        if source_type not in buckets:
            continue

        known_entity = obs.get("entity")
        for item in obs.get("items") or []:
            key = (source_type, item.get("url") or "", item.get("title") or "")
            if key in seen:
                continue
            seen.add(key)

            buckets[source_type].append({
                "title": item.get("title", "Untitled"),
                "snippet": item.get("snippet", ""),
                "source_name": item.get("source_name", "Unknown source"),
                "date": item.get("date", "Recent"),
                "url": item.get("url", "#"),
                "entity": known_entity or infer_entity(item, comp_list),
            })

    return [{"source_type": s, "items": buckets[s]} for s in SECTION_ORDER]


def compute_gap_report(sections: List[Dict[str, Any]], comp_list: List[str]) -> List[Dict[str, Any]]:
    """
    Flags competitors with thin coverage, counted from real retrieved items.

    Computed rather than model-generated so the entity names always match the requested
    competitors and can be fed straight back into targeted gap-fill searches.
    """
    counts = {c: 0 for c in comp_list}
    for section in sections:
        for item in section["items"]:
            entity = item.get("entity")
            if entity in counts:
                counts[entity] += 1

    gaps = []
    for comp in comp_list:
        if counts[comp] < GAP_THRESHOLD:
            gaps.append({
                "entity": comp,
                "gap": f"Thin coverage ({counts[comp]} grounded item(s) retrieved). Recommended targeted gap-fill search.",
                "item_count": counts[comp],
            })
    return gaps


class FieldAgent:
    """
    Field Research Agent.
    Executes raw tool calls (news, research, patents, github, reddit) and returns grounded observations.
    Does NOT synthesize summaries or conclusions.
    """
    def __init__(self, model: Optional[str] = None):
        self.model_name = resolve_model(model)
        self.role_name = "Field Agent"

    def execute_targeted_followup(self, question: str, max_items: int = 3) -> Dict[str, Any]:
        """
        Executes exactly ONE targeted tool call triggered by a user follow-up question.
        Returns the action, the raw observation text, and the structured items behind it.
        """
        q_lower = question.lower()
        if "patent" in q_lower:
            tool_name, result = "search_patents", search_patents(question, max_results=max_items)
        elif "news" in q_lower or "funding" in q_lower or "announce" in q_lower:
            tool_name, result = "search_news", search_news(question, max_results=max_items)
        elif "github" in q_lower or "code" in q_lower or "repo" in q_lower:
            tool_name, result = "search_github", search_github(question, max_results=max_items)
        elif "reddit" in q_lower or "sentiment" in q_lower or "user" in q_lower:
            tool_name, result = "search_reddit", search_reddit(question, max_results=max_items)
        else:
            tool_name, result = "search_semantic_scholar", search_semantic_scholar(question, max_results=max_items)

        return {
            "action": f"{tool_name}(\"{question}\")",
            "observation": result["text"],
            "items": result["items"],
            "source_type": result["source_type"],
        }

    def _run_tool(self, tool_fn, query: str, thought: str, step: int, max_items: int,
                  entity: Optional[str] = None) -> Generator[Dict[str, Any], None, None]:
        """Yields a step_start/step_complete pair around a single grounded tool call."""
        action = f"{tool_fn.__name__}(\"{query}\")"
        yield {
            "type": "step_start",
            "agent_role": self.role_name,
            "step": step,
            "thought": thought,
            "action": action,
        }

        try:
            result = tool_fn(query, max_results=max_items)
        except Exception as e:
            logger.error(f"[Field Agent] Tool {tool_fn.__name__} failed for query '{query}': {e}")
            result = {
                "text": f"[Tool Error]: {tool_fn.__name__} failed for query '{query}': {e}",
                "items": [],
                "source_type": None,
            }

        yield {
            "type": "step_complete",
            "agent_role": self.role_name,
            "step": step,
            "thought": thought,
            "action": action,
            "observation": result["text"],
            "items": result["items"],
            "source_type": result["source_type"],
            "entity": entity,
        }

    def gather_observations_stream(self, topic: str, competitors: str, max_items: int = 5, start_step: int = 1,
                                   is_gap_fill: bool = False, gap_entities: Optional[List[str]] = None,
                                   step_budget: Optional[int] = None) -> Generator[Dict[str, Any], None, None]:
        clean_topic = topic.strip() or "Regional language capabilities for AI"
        clean_comps = competitors.strip() or "Sarvam, OpenAI, Google"
        comp_list = [c.strip() for c in clean_comps.split(",") if c.strip()]
        if not comp_list:
            comp_list = [clean_topic]

        step = start_step
        budget_end = start_step + step_budget if step_budget is not None else None

        def out_of_budget() -> bool:
            if budget_end is None:
                return False
            if step >= budget_end:
                logger.info(f"[Field Agent] Step budget reached at step {step}; halting further tool calls.")
                return True
            return False

        if is_gap_fill and gap_entities:
            # GAP-FILL MODE: one targeted news search per entity flagged in the gap report
            for entity in gap_entities:
                if out_of_budget():
                    return
                query = f"{entity} {clean_topic}".strip()
                thought = f"Targeted Gap-Fill: Field Agent re-querying '{entity}' to address thin observation coverage."
                yield from self._run_tool(search_news, query, thought, step, max_items, entity=entity)
                step += 1
            return

        # STANDARD INITIAL FIELD SCAN

        # 1. News per competitor
        for comp in comp_list:
            if out_of_budget():
                return
            yield from self._run_tool(
                search_news, f"{comp} {clean_topic}".strip(),
                f"Field Agent collecting live market news for competitor '{comp}'.",
                step, max_items, entity=comp
            )
            step += 1

        # 2. Academic papers
        if out_of_budget():
            return
        yield from self._run_tool(
            search_semantic_scholar, clean_topic,
            f"Field Agent collecting academic literature for '{clean_topic}'.",
            step, max_items
        )
        step += 1

        # 3. Patent filings
        if out_of_budget():
            return
        yield from self._run_tool(
            search_patents, clean_topic,
            f"Field Agent querying patent filings for '{clean_topic}'.",
            step, max_items
        )
        step += 1

        # 4. GitHub open source repos
        if out_of_budget():
            return
        yield from self._run_tool(
            search_github, f"{clean_topic} open source".strip(),
            f"Field Agent checking GitHub repositories for '{clean_topic}'.",
            step, max_items
        )
        step += 1

        # 5. Reddit community sentiment per competitor
        for comp in comp_list:
            if out_of_budget():
                return
            yield from self._run_tool(
                search_reddit, f"{comp} user feedback".strip(),
                f"Field Agent parsing Reddit discussions for competitor '{comp}'.",
                step, max_items, entity=comp
            )
            step += 1


class AnalystAgent:
    """
    Strategic Analyst Agent.

    Writes the executive summary prose from the Field Agent's grounded observations. The findings
    list and the coverage gap report are computed deterministically elsewhere, so the model never
    produces citations, URLs, or entity names of its own.
    """
    def __init__(self, model: Optional[str] = None):
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.model_name = resolve_model(model)
        self.role_name = "Analyst Agent"

    @property
    def llm_enabled(self) -> bool:
        return llm_available()

    def synthesize_summary(self, topic: str, competitors: str, observations: List[Dict[str, Any]],
                           sections: List[Dict[str, Any]], gap_report: List[Dict[str, Any]]) -> str:
        """Returns the executive takeaway prose, falling back to a deterministic summary."""
        obs_text_blocks = [
            f"--- OBSERVATION (Action: {o.get('action')}) ---\n{o.get('observation')}"
            for o in observations
            if o.get("type") == "step_complete" and o.get("observation")
        ]
        total_items = sum(len(s["items"]) for s in sections)

        if self.llm_enabled and obs_text_blocks:
            combined_obs_text = "\n\n".join(obs_text_blocks)
            gap_text = json.dumps(gap_report, indent=2) if gap_report else "None — all competitors met the coverage threshold."
            prompt_content = (
                f"Topic: {topic}\n"
                f"Competitors: {competitors}\n\n"
                f"PRECOMPUTED COVERAGE GAP REPORT:\n{gap_text}\n\n"
                f"GROUNDED OBSERVATIONS:\n{combined_obs_text[:6000]}"
            )

            logger.info(f"[Analyst] Requesting Gemini synthesis (model='{self.model_name}', observations={len(obs_text_blocks)}).")
            raw = call_gemini(prompt_content, ANALYST_AGENT_PROMPT, self.model_name, json_mode=True)

            if raw:
                try:
                    clean_json = raw.strip()
                    if "```" in clean_json:
                        clean_json = clean_json.split("```json")[-1].split("```")[0].strip()
                    parsed = json.loads(clean_json)
                    takeaway = (parsed.get("executive_takeaway") or parsed.get("executive_summary") or "").strip()
                    if takeaway:
                        return takeaway
                    logger.warning("[Analyst] Gemini response contained no executive_takeaway; using fallback summary.")
                except (json.JSONDecodeError, AttributeError) as e:
                    logger.warning(f"[Analyst] Could not parse Gemini JSON response ({e}); using fallback summary.")
        elif not self.llm_enabled:
            logger.info("[Analyst] LLM synthesis unavailable (no API key or SDK); using deterministic summary.")

        # Deterministic fallback summary
        per_source = ", ".join(
            f"{len(s['items'])} {s['source_type']}" for s in sections if s["items"]
        ) or "no retrievable signals"
        return (
            f"Strategic analyst synthesis for '{topic}' across {competitors}. "
            f"Retrieved {total_items} grounded items ({per_source}) from {len(obs_text_blocks)} field observations. "
            f"Coverage gap analysis flagged {len(gap_report)} "
            f"{'entity' if len(gap_report) == 1 else 'entities'} as requiring deeper inspection."
        )


CHAT_AGENT_PROMPT = """You are the Strategic Analyst Agent answering follow-up questions about an intelligence scan.

You are given the findings retrieved during the scan, the conversation so far, and optionally a fresh
real-time field observation. Answer in 2-4 sentences, citing the specific findings you relied on by
title or source.

CRITICAL MANDATE: Use only the supplied findings and observations. Never introduce outside facts and
never invent titles, sources, or URLs. If the supplied context does not answer the question, say so
directly and name what additional lookup would be needed.
"""


def format_context_items(label: str, items: List[Dict[str, Any]], limit: int = 8) -> str:
    """Renders scan findings into a compact cited block for the chat prompt."""
    if not items:
        return ""
    lines = [f"\n{label}:"]
    for item in items[:limit]:
        title = item.get("title") or item.get("name") or "Untitled"
        source = item.get("source_name") or item.get("source") or "Unknown source"
        date = item.get("date") or item.get("published") or "Recent"
        snippet = (item.get("snippet") or item.get("summary") or item.get("description") or "").strip()
        entity = item.get("entity")
        entity_tag = f" [entity: {entity}]" if entity and entity != "General" else ""
        lines.append(f"- {title} ({source}, {date}){entity_tag}")
        if snippet:
            lines.append(f"  {snippet[:200]}")
    if len(items) > limit:
        lines.append(f"  ... and {len(items) - limit} further items not shown.")
    return "\n".join(lines)


def synthesize_chat_answer(question: str, chat_history: List[Dict[str, str]],
                           context_blocks: str, tool_res: Optional[Dict[str, Any]],
                           model: Optional[str] = None) -> Optional[str]:
    """
    Answers an analyst follow-up question over the scan findings.

    Returns None when no LLM is available so the caller can fall back to a grounded,
    non-generated response.
    """
    model_name = resolve_model(model)

    history_context = ""
    if chat_history:
        history_context = "\n\nCONVERSATION HISTORY:\n" + "\n".join(
            f"{m.get('role', 'user').upper()}: {m.get('content', '')}" for m in chat_history[-6:]
        )

    scan_context = f"\n\nSCAN FINDINGS AVAILABLE TO YOU:{context_blocks}" if context_blocks else (
        "\n\nSCAN FINDINGS AVAILABLE TO YOU: none — no scan has been run in this session yet."
    )

    tool_context = ""
    if tool_res:
        tool_context = (
            f"\n\nREAL-TIME TARGETED FIELD OBSERVATION (triggered by this follow-up):\n"
            f"Action: {tool_res['action']}\nObservation:\n{tool_res['observation'][:2500]}"
        )

    prompt = (
        f"{scan_context}"
        f"{history_context}"
        f"{tool_context}\n\n"
        f"USER FOLLOW-UP QUESTION: {question}"
    )

    logger.info(f"[Chat] Requesting Gemini answer (model='{model_name}', history_turns={len(chat_history)}).")
    return call_gemini(prompt, CHAT_AGENT_PROMPT, model_name, json_mode=False, temperature=0.3)


class OrchestratorAgent:
    """
    Orchestrates the multi-agent execution loop:
    1. Memory Recall: reads SQLite long-term memory for the baseline.
    2. Field Agent gathers initial observations across all competitors.
    3. Findings and the coverage gap report are computed from the real retrieved items.
    4. If gaps exist, Field Agent runs one targeted gap-fill pass.
    5. Analyst Agent writes the executive summary; the delta vs. prior memory is computed and stored.
    """
    def __init__(self, model: Optional[str] = None):
        self.field_agent = FieldAgent(model)
        self.analyst_agent = AnalystAgent(model)

    def stream_orchestration(self, topic: str, competitors: str, max_items: int = 5, max_steps: int = 12) -> Generator[str, None, None]:
        comp_list = [c.strip() for c in competitors.split(",") if c.strip()]
        primary_comp = comp_list[0] if comp_list else topic

        # STEP 0: Long-Term Memory Recall
        prior_mem = get_prior_scan_memory(topic, primary_comp)
        if prior_mem:
            scope = "" if prior_mem.get("topic_match") else f" (recorded under a different topic: '{prior_mem['topic']}')"
            mem_content = f"Loaded prior gap report for {primary_comp} from {prior_mem['timestamp']}{scope}."
        else:
            mem_content = f"First recorded scan for {primary_comp}. Initializing long-term memory baseline."

        yield json.dumps({
            "type": "memory_recall",
            "agent_role": "Orchestrator",
            "step": 0,
            "thought": "Querying SQLite long-term scan memory for prior competitor benchmarks.",
            "action": f"memory_db.get_prior_scan_memory(\"{topic}\", \"{primary_comp}\")",
            "content": mem_content,
            "delta": "Pending — computed once this scan completes.",
            "prior_memory": prior_mem
        }) + "\n"

        observations: List[Dict[str, Any]] = []
        step_counter = 1
        # max_steps bounds tool calls; the two analyst steps sit outside that budget
        remaining_budget = max(1, max_steps)

        # PASS 1: Field Agent Initial Observation Gathering
        logger.info("--- [ORCHESTRATOR] Pass 1: Field Agent Gathering Grounded Observations ---")
        for chunk in self.field_agent.gather_observations_stream(
            topic, competitors, max_items, start_step=step_counter, step_budget=remaining_budget
        ):
            yield json.dumps(chunk) + "\n"
            if chunk.get("type") == "step_complete":
                observations.append(chunk)
                step_counter += 1

        remaining_budget = max(0, max_steps - (step_counter - 1))

        # Findings and gaps are computed from real retrieved items, not model output
        sections = build_sections(observations, comp_list)
        gap_report = compute_gap_report(sections, comp_list)

        t_analyst = f"Analyst Agent evaluating {len(observations)} field observations for coverage gaps."
        a_analyst = "compute_gap_report(sections)"
        yield json.dumps({
            "type": "step_start",
            "agent_role": "Analyst Agent",
            "step": step_counter,
            "thought": t_analyst,
            "action": a_analyst
        }) + "\n"

        gap_entities = [g["entity"] for g in gap_report]
        yield json.dumps({
            "type": "step_complete",
            "agent_role": "Analyst Agent",
            "step": step_counter,
            "thought": t_analyst,
            "action": a_analyst,
            "observation": (
                f"Evaluation complete. Retrieved {sum(len(s['items']) for s in sections)} grounded items. "
                f"Found {len(gap_report)} coverage gap(s): {gap_entities or 'none'}"
            )
        }) + "\n"
        step_counter += 1

        # GAP-FILL: at most one round, and only if step budget remains
        if gap_report and remaining_budget > 0:
            logger.info(f"--- [ORCHESTRATOR] Gap-Fill Round: {len(gap_report)} flagged entities ---")
            for chunk in self.field_agent.gather_observations_stream(
                topic, competitors, max_items, start_step=step_counter,
                is_gap_fill=True, gap_entities=gap_entities, step_budget=remaining_budget
            ):
                yield json.dumps(chunk) + "\n"
                if chunk.get("type") == "step_complete":
                    observations.append(chunk)
                    step_counter += 1

            # Recompute findings and gaps over the combined observation set
            sections = build_sections(observations, comp_list)
            gap_report = compute_gap_report(sections, comp_list)
        elif gap_report:
            logger.info(f"--- [ORCHESTRATOR] Gap-fill skipped: step budget ({max_steps}) exhausted ---")

        # FINAL SYNTHESIS
        t_final = "Analyst Agent writing executive synthesis over the grounded observation set."
        a_final = "synthesize_summary()"
        yield json.dumps({
            "type": "step_start",
            "agent_role": "Analyst Agent",
            "step": step_counter,
            "thought": t_final,
            "action": a_final
        }) + "\n"

        executive_takeaway = self.analyst_agent.synthesize_summary(
            topic, competitors, observations, sections, gap_report
        )

        yield json.dumps({
            "type": "step_complete",
            "agent_role": "Analyst Agent",
            "step": step_counter,
            "thought": t_final,
            "action": a_final,
            "observation": "Final Analyst Agent synthesis complete."
        }) + "\n"

        # Memory delta is computed here — after the scan — against this run's gap report
        current_item_count = sum(len(s["items"]) for s in sections)
        mem_delta = compute_memory_delta(prior_mem, primary_comp, gap_report, current_item_count)

        yield json.dumps({
            "type": "memory_update",
            "agent_role": "Orchestrator",
            "step": 0,
            "content": mem_content,
            "delta": mem_delta
        }) + "\n"

        save_scan_memory(
            topic=topic,
            competitor=primary_comp,
            gap_report=gap_report,
            executive_summary=executive_takeaway
        )

        structured_output = {
            "executive_takeaway": executive_takeaway,
            "gap_report": gap_report,
            "sections": sections,
        }
        by_type = {s["source_type"]: s["items"] for s in sections}

        yield json.dumps({
            "type": "final_complete",
            "status": "success",
            "topic": topic,
            "competitors": competitors,
            "structured_output": structured_output,
            "final_answer": executive_takeaway,
            "executive_report": executive_takeaway,
            "gap_report": gap_report,
            "memory_recall": {
                "content": mem_content,
                "delta": mem_delta
            },
            "papers": by_type.get("research", []),
            "news": by_type.get("news", []),
            "patents": by_type.get("patents", []),
            "github_repos": by_type.get("github", []),
            "reddit_posts": by_type.get("reddit", []),
            "model_used": self.analyst_agent.model_name if self.analyst_agent.llm_enabled else "rule-based-fallback",
            "llm_active": self.analyst_agent.llm_enabled
        }) + "\n"


class AutonomousReActAgent:
    """
    Backwards-compatible interface wrapper routing to OrchestratorAgent.
    """
    def __init__(self, model: Optional[str] = None):
        self.orchestrator = OrchestratorAgent(model)
        self.field_agent = FieldAgent(model)

    def stream_scan(self, topic: str = "Regional language capabilities for AI", competitors: str = "Sarvam, OpenAI, Google", max_items: int = 5, max_steps: int = 12) -> Generator[str, None, None]:
        return self.orchestrator.stream_orchestration(topic, competitors, max_items, max_steps)

    def run_scan(self, topic: str = "Regional language capabilities for AI", competitors: str = "Sarvam, OpenAI, Google", max_items: int = 5, max_steps: int = 12) -> Dict[str, Any]:
        stream_results = list(self.stream_scan(topic, competitors, max_items, max_steps))
        if not stream_results:
            raise RuntimeError("Scan produced no output.")

        events = [json.loads(line) for line in stream_results]
        final = next((e for e in reversed(events) if e.get("type") == "final_complete"), None)
        if final is None:
            raise RuntimeError("Scan did not produce a final_complete event.")

        memory_delta = final.get("memory_recall", {}).get("delta")

        trace: List[Dict[str, Any]] = []
        for data in events:
            etype = data.get("type")
            if etype == "step_complete":
                trace.append({
                    "step": data["step"],
                    "agent_role": data.get("agent_role", "Field Agent"),
                    "thought": data["thought"],
                    "action": data["action"],
                    "observation": data["observation"]
                })
            elif etype == "memory_recall":
                trace.append({
                    "step": 0,
                    "agent_role": "Orchestrator",
                    "step_type": "memory_recall",
                    "thought": data["thought"],
                    "action": data["action"],
                    "content": data["content"],
                    # the resolved delta, not the "pending" placeholder
                    "delta": memory_delta or data["delta"]
                })

        return {
            "status": "success",
            "topic": final["topic"],
            "competitors": final["competitors"],
            "structured_output": final["structured_output"],
            "final_answer": final["final_answer"],
            "executive_report": final["executive_report"],
            "gap_report": final.get("gap_report", []),
            "memory_recall": final.get("memory_recall", {}),
            "papers": final["papers"],
            "news": final["news"],
            "patents": final.get("patents", []),
            "github_repos": final.get("github_repos", []),
            "reddit_posts": final.get("reddit_posts", []),
            "trace": trace,
            "llm_active": final.get("llm_active", False),
            "model_used": final.get("model_used", "")
        }
