"""Chaos injection for the adversarial demo.

The judging rubric asks for failure recovery that is *demonstrable*, and the only
honest way to demonstrate a recovery path on stage is to break something on
purpose. That is what this module is for, and it is fenced off accordingly:

  * Nothing here activates unless ``chaos_mode`` is explicitly present in the
    request. There is no env var, no default, and no sampling.
  * Every injection writes a ``chaos`` entry to ``trace_log`` labelled as a
    deliberate demo trigger, so a chaos-induced failure can never be read as a
    real one — by a judge, or by us at 3am.
  * Injections wrap real code paths rather than replacing them. A chaos tool
    failure raises from inside the same ``try`` the real tool raises from, so the
    recovery that runs is the production recovery, not a rehearsal of it.

Modes
-----
``tool_failure``
    ``search_patents`` raises. Exercises tool fallback + trace labelling.
``conflicting_evidence``
    Injects one fabricated observation that contradicts a real retrieved claim.
    Exercises ``conflict_check`` and forces the analyst to address it. The
    injected item is stamped ``fabricated: True`` and carries a non-http url so
    it can never be presented as a citation.
``budget_exhaustion``
    Zeroes the tool-call budget after the first competitor's fan-out. Exercises
    resource-aware degradation.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

TOOL_FAILURE = "tool_failure"
CONFLICTING_EVIDENCE = "conflicting_evidence"
BUDGET_EXHAUSTION = "budget_exhaustion"

VALID_MODES = (TOOL_FAILURE, CONFLICTING_EVIDENCE, BUDGET_EXHAUSTION)

# The tool chaos targets. Patents is chosen because it is the one source with a
# real three-tier fallback ladder behind it, so the recovery is substantive.
CHAOS_TOOL_TARGET = "search_patents"


class ChaosToolFailure(RuntimeError):
    """Raised by an intentionally-broken tool. Named so logs never read as a real outage."""


def normalize(requested: Optional[List[str]]) -> List[str]:
    """Keeps only recognised modes, so an unknown string cannot silently enable chaos."""
    if not requested:
        return []
    modes = [m.strip().lower() for m in requested if isinstance(m, str) and m.strip()]
    accepted = [m for m in modes if m in VALID_MODES]
    rejected = [m for m in modes if m not in VALID_MODES]
    if rejected:
        logger.warning(f"[Chaos] Ignoring unrecognised chaos mode(s): {rejected}")
    if accepted:
        logger.warning(f"[Chaos] DEMO MODE ACTIVE - deliberate fault injection enabled: {accepted}")
    return accepted


def active(modes: List[str], mode: str) -> bool:
    return mode in (modes or [])


def maybe_break_tool(modes: List[str], tool_name: str) -> None:
    """
    Raises if this tool is the chaos target. Called at the top of the real tool
    wrapper so the failure enters the same recovery path a genuine outage would.
    """
    if active(modes, TOOL_FAILURE) and tool_name == CHAOS_TOOL_TARGET:
        raise ChaosToolFailure(
            f"[CHAOS DEMO] {tool_name} was made to fail on purpose by chaos_mode='{TOOL_FAILURE}'. "
            f"This is not a real outage."
        )


def fabricate_conflict(observations: List[Dict[str, Any]], comp_list: List[str]) -> Optional[Dict[str, Any]]:
    """
    Builds one observation that contradicts a real retrieved claim.

    It anchors on a real item so the contradiction is about something actually in
    the evidence set — a free-floating fake claim would not exercise the
    cross-source comparison in ``conflict_check`` at all.

    Returns None when there is no real item to contradict; a fabricated conflict
    with nothing to conflict against would be theatre.
    """
    anchor = None
    for obs in observations:
        for item in obs.get("items") or []:
            if (item.get("title") or "").strip():
                anchor = (obs, item)
                break
        if anchor:
            break
    if not anchor:
        return None

    source_obs, item = anchor
    entity = source_obs.get("entity") or (comp_list[0] if comp_list else "the subject")
    real_title = item["title"]

    fabricated_item = {
        "title": f"[CHAOS DEMO - FABRICATED] Report disputes {entity} claims",
        "snippet": (
            f"Contradicts the retrieved item '{real_title[:90]}'. This fabricated source states that "
            f"{entity} has SHUT DOWN the programme and that adoption FELL to 12 deployments, "
            f"against the retrieved evidence describing a launch and growth. "
            f"Injected deliberately by chaos_mode='{CONFLICTING_EVIDENCE}'."
        ),
        "source_name": "CHAOS DEMO - fabricated source (not real evidence)",
        "date": item.get("date") or "Recent",
        # Deliberately not an http(s) url: the frontend and every citation check
        # treat non-http as unusable, so this can never render as a real citation.
        "url": "chaos://fabricated/not-a-real-source",
        "fabricated": True,
    }

    return {
        "type": "step_complete",
        "agent_role": "Chaos Injector",
        "chaos": True,
        "step_type": "chaos",
        "thought": f"[CHAOS DEMO] Injecting a fabricated observation that contradicts '{real_title[:60]}'.",
        "action": f"chaos.fabricate_conflict(mode='{CONFLICTING_EVIDENCE}')",
        "observation": (
            f"[CHAOS DEMO - FABRICATED OBSERVATION] A contradicting claim about {entity} was inserted "
            f"on purpose to exercise conflict resolution. It is not real evidence."
        ),
        "items": [fabricated_item],
        "source_type": "news",
        "entity": entity,
        "fabricated": True,
    }
