"""
Evaluation harness: one normal scan, one deliberately broken scan, one report.

Run it with no arguments:

    python eval_and_trace.py

It runs the agent twice over the same topic — once normally, once with
``chaos_mode=tool_failure`` — and measures latency, tool calls, LLM token usage,
errors and task success for each. It then prints a before/after table and writes
``eval_report.md`` at the repository root.

The agent is driven in-process rather than over HTTP for two reasons: the token
counters in ``agent_brain`` live in this process, and the tier-level recovery
messages the patent tool logs are the actual evidence of what failed and how it
recovered. Both would otherwise have to be scraped out of a server log.

Both runs hit live third-party APIs, so absolute latency reflects the network on
the day. What the comparison is for is whether the injected failure changes the
outcome, not whether the second run is a few seconds slower.
"""

import io
import json
import logging
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

import agent_brain
from agent_brain import AutonomousReActAgent

load_dotenv()

# Small on purpose: this is a diagnostic, not a demo scan. One competitor with a
# budget of 8 still clears the 4*N + 3 calls a full fan-out needs, so every
# source runs and the patent step — the chaos target — is guaranteed to execute.
TOPIC = os.getenv("EVAL_TOPIC", "Indian language AI models")
COMPETITORS = os.getenv("EVAL_COMPETITORS", "Sarvam AI")
MAX_ITEMS = int(os.getenv("EVAL_MAX_ITEMS", "3"))
MAX_STEPS = int(os.getenv("EVAL_MAX_STEPS", "8"))

REPORT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "eval_report.md")

# A tier that raised and was fallen through, logged by tools/patent_tool.py.
TIER_RAISED = re.compile(r"Tier '([^']+)' raised, falling through")
# An LLM attempt that failed, logged by agent_brain.call_gemini.
LLM_FAILED = re.compile(r"\[Gemini\] Model '[^']+' failed")
# The source label the successful tier stamps on its observation, e.g.
# "[Google Patents WEB SEARCH fallback (...)]: Found 2 patent records...".
SOURCE_LABEL = re.compile(r"^\[([^\]]+)\]")


class LogCapture(logging.Handler):
    """Collects log messages in memory so a run's own logs become measurable data."""

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.lines: List[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.lines.append(record.getMessage())
        except Exception:  # pragma: no cover - never let logging break the harness
            pass


def _configure_logging(capture: LogCapture) -> None:
    """
    Routes every log record to the capture handler and nowhere else.

    Console output is suppressed deliberately: this harness prints its own
    progress, and tool output is arbitrary third-party text that can raise
    UnicodeEncodeError on a Windows cp1252 console mid-scan.
    """
    logging.basicConfig(level=logging.INFO, handlers=[capture], force=True)


def measure(label: str, chaos_modes: Optional[List[str]]) -> Dict[str, Any]:
    """Runs one scan and returns its metrics. Never raises; a crash is a result too."""
    capture = LogCapture()
    _configure_logging(capture)
    agent_brain.reset_token_usage()

    print(f"[{label}] running (topic={TOPIC!r}, competitors={COMPETITORS!r}, "
          f"max_items={MAX_ITEMS}, max_steps={MAX_STEPS}, chaos={chaos_modes or 'none'})...")

    agent = AutonomousReActAgent(chaos_modes=chaos_modes)
    events: List[Dict[str, Any]] = []
    crash: Optional[str] = None

    start = time.perf_counter()
    try:
        for line in agent.stream_scan(
            topic=TOPIC, competitors=COMPETITORS, max_items=MAX_ITEMS, max_steps=MAX_STEPS
        ):
            line = line.strip()
            if line:
                events.append(json.loads(line))
    except Exception as e:
        crash = f"{type(e).__name__}: {e}"
    latency = time.perf_counter() - start

    completions = [e for e in events if e.get("type") == "step_complete"]
    # Analyst steps also emit step_complete pairs; only Field Agent steps are tool calls.
    tool_steps = [e for e in completions if e.get("agent_role") == "Field Agent"]
    final = next((e for e in reversed(events) if e.get("type") == "final_complete"), None)

    sections = ((final or {}).get("structured_output") or {}).get("sections") or []
    findings = sum(len(s.get("items") or []) for s in sections)
    takeaway = ((final or {}).get("structured_output") or {}).get("executive_takeaway") or ""

    # A tool that raised with nothing left to try. This is the number that must stay 0.
    hard_errors = [e for e in completions if str(e.get("observation", "")).startswith("[Tool Error]")]
    # A tool that raised but was recovered by a lower tier. Degradation, not failure.
    recovered = [m.group(1) for line in capture.lines for m in [TIER_RAISED.search(line)] if m]
    empty_tools = [e for e in tool_steps if not e.get("items")]
    # An LLM call that failed is a soft failure: synthesis degrades to the
    # deterministic analyst, so the scan still succeeds. Counted separately from
    # tool errors for exactly that reason.
    llm_failed = sum(1 for line in capture.lines if LLM_FAILED.search(line))
    quota_exhausted = any("RESOURCE_EXHAUSTED" in line for line in capture.lines)
    chaos_steps = [e for e in completions if e.get("chaos")]

    serving_label = None
    patent_step = next((e for e in tool_steps if e.get("source_type") == "patents"), None)
    if patent_step:
        match = SOURCE_LABEL.match(str(patent_step.get("observation", "")))
        label_text = match.group(1) if match else None
        # "[Patent Observation]" is the no-records path's own label, not a tier that
        # served data, so it must not be reported as the serving source.
        serving_label = None if label_text == "Patent Observation" else label_text

    return {
        "label": label,
        "chaos_modes": chaos_modes or [],
        "latency_s": round(latency, 1),
        "tool_calls": len(tool_steps),
        "findings": findings,
        "hard_errors": len(hard_errors),
        "recovered_tiers": recovered,
        "empty_tools": len(empty_tools),
        "chaos_steps": len(chaos_steps),
        "tokens": agent_brain.get_token_usage(),
        "llm_active": bool((final or {}).get("llm_active")),
        "llm_failed": llm_failed,
        "quota_exhausted": quota_exhausted,
        "patent_items": len(patent_step.get("items") or []) if patent_step else 0,
        "patent_source": serving_label,
        "crash": crash,
        # Success is the whole task, not just a 200: the scan finished, it produced
        # grounded findings, no tool died unrecovered, and the analyst wrote something.
        "task_success": bool(final) and findings > 0 and not hard_errors and len(takeaway) > 40 and crash is None,
    }


def recovery_sentence(chaos: Dict[str, Any]) -> str:
    """One sentence on what failed and how it recovered, from this run's own trace."""
    if not chaos["chaos_steps"]:
        return (
            "No chaos step was recorded, so the injected failure never reached "
            "search_patents — treat this run as inconclusive rather than as a pass."
        )
    tiers = " and ".join(dict.fromkeys(chaos["recovered_tiers"])) or "the authoritative tiers"
    if not chaos["patent_items"]:
        return (
            f"search_patents was forced to fail: the {tiers} tier(s) raised ChaosToolFailure and the "
            f"remaining tier returned nothing, so the patent step reported coverage as unavailable "
            f"rather than claiming no patents exist, and the scan still completed with "
            f"{chaos['findings']} findings from the other sources."
        )
    return (
        f"search_patents was forced to fail: the {tiers} tier(s) raised ChaosToolFailure, the existing "
        f"three-tier ladder fell through to {chaos['patent_source'] or 'the web-search tier'}, which "
        f"returned {chaos['patent_items']} real patent records, and the scan completed with "
        f"{chaos['findings']} findings and {chaos['hard_errors']} unrecovered errors."
    )


def build_report(normal: Dict[str, Any], chaos: Dict[str, Any]) -> str:
    def row(name: str, fn) -> str:
        return f"| {name} | {fn(normal)} | {fn(chaos)} |"

    def tok(run: Dict[str, Any]) -> str:
        t = run["tokens"]
        if t["calls"]:
            return f"{t['total_tokens']} ({t['calls']} calls)"
        if run["llm_active"]:
            return f"0 ({run['llm_failed']} LLM calls failed)"
        return "0 (no key or SDK)"

    def analyst_path(run: Dict[str, Any]) -> str:
        return "Gemini" if run["tokens"]["calls"] else "deterministic fallback"

    lines = [
        "| Metric | Normal | chaos_mode=tool_failure |",
        "| :--- | ---: | ---: |",
        row("Latency (s)", lambda r: r["latency_s"]),
        row("Tool calls", lambda r: r["tool_calls"]),
        row("Findings retrieved", lambda r: r["findings"]),
        row("Unrecovered errors", lambda r: r["hard_errors"]),
        row("Recovered tier failures", lambda r: len(r["recovered_tiers"])),
        row("Tools returning nothing", lambda r: r["empty_tools"]),
        row("Total tokens", tok),
        row("Analyst path", analyst_path),
        row("Patent records", lambda r: r["patent_items"]),
        row("Patent source served by", lambda r: r["patent_source"] or "none (unavailable)"),
        row("Task success", lambda r: "PASS" if r["task_success"] else "FAIL"),
    ]
    table = "\n".join(lines)

    llm_note = ""
    if normal["quota_exhausted"] or chaos["quota_exhausted"]:
        llm_note = (
            "\n> **Note:** the Gemini key hit its free-tier daily request quota (HTTP 429 "
            "`RESOURCE_EXHAUSTED`) during this run, so both scans synthesized with the "
            "deterministic analyst. Token instrumentation is live; there was simply no "
            "successful LLM call to count. Re-run once the quota resets for populated token counts.\n"
        )

    return f"""# IntelPulse Evaluation & Trace

Generated by `backend/eval_and_trace.py`. Two live scans over the same input —
topic `{TOPIC}`, competitors `{COMPETITORS}`, `max_items={MAX_ITEMS}`, `max_steps={MAX_STEPS}` —
one normal, one with the patent tool deliberately broken.

## Before / after

{table}

## What failed and how it recovered

{recovery_sentence(chaos)}

## Reading the numbers

- **Unrecovered errors** counts tools that raised with no fallback left. It is the number that
  has to stay at 0 in both columns; a recovered tier failure is degradation, not failure.
- **Tools returning nothing** is not an error. A source with no matching results is reported as
  empty, and an unreachable source is reported as unavailable — the two are never conflated.
- Latency covers live third-party APIs and LLM synthesis, so it moves with the network. The
  chaos column is expected to be slower: it walks further down the patent ladder before it wins.
- Token counts come from Gemini's own `usage_metadata`, accumulated per run in `agent_brain`.
  A zero with failed calls means synthesis degraded to the deterministic analyst — which is why
  task success can still be PASS: an LLM outage costs narrative quality, not the findings.
{llm_note}"""


def main() -> int:
    normal = measure("normal", None)
    chaos = measure("chaos", ["tool_failure"])

    report = build_report(normal, chaos)
    io.open(REPORT_PATH, "w", encoding="utf-8", newline="\n").write(report)

    # Print the report body itself: the table and the one-sentence finding are the
    # deliverable, so the console and the file should not be able to disagree.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print()
    print(report)
    print(f"Written to {REPORT_PATH}")

    for run in (normal, chaos):
        if run["crash"]:
            print(f"[{run['label']}] CRASHED: {run['crash']}")

    return 0 if normal["task_success"] and chaos["task_success"] else 1


if __name__ == "__main__":
    sys.exit(main())
