"""Live contract smoke test for every research tool.

Every tool must return a dict shaped as:
    {"text": str, "items": [{title, snippet, source_name, date, url}], "source_type": str}

`text` is the observation string handed to the LLM; `items` is the structured
evidence the backend uses to build the findings list deterministically. Run with:

    cd backend && python test_audit_tools.py

Network access is required. Missing optional API keys are not failures — tools
fall back to public feeds and label themselves accordingly.
"""

import logging
import sys

from tools.competitor_tool import search_news
from tools.github_tool import search_github
from tools.hf_tool import search_huggingface_models
from tools.hn_tool import search_hackernews
from tools.patent_tool import search_patents
from tools.reddit_tool import search_reddit
from tools.research_tool import search_semantic_scholar

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

# Live API text is not guaranteed to fit the console codec (a Windows cp1252
# terminal cannot encode a curly quote or an emoji in a repo description).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ITEM_KEYS = ("title", "snippet", "source_name", "date", "url")

CASES = [
    ("search_news", lambda: search_news("Sarvam AI", max_results=5), "news"),
    (
        "search_semantic_scholar",
        lambda: search_semantic_scholar("low-resource language model", max_results=5),
        "research",
    ),
    ("search_patents", lambda: search_patents("speech recognition", max_results=5), "patents"),
    ("search_github", lambda: search_github("indic llm", max_results=5), "github"),
    ("search_reddit", lambda: search_reddit("Sarvam AI", max_results=5), "reddit"),
    (
        "search_huggingface_models",
        lambda: search_huggingface_models("sarvam", max_results=5),
        "models",
    ),
    ("search_hackernews", lambda: search_hackernews("Sarvam AI", max_results=5), "hackernews"),
]

# Kept in step with SECTION_ORDER in agent_brain.py: a tool whose source_type is
# not a known section is silently discarded by build_sections, so the test asserts
# the set of covered types rather than trusting the CASES list to stay complete.
EXPECTED_SOURCE_TYPES = {"news", "research", "patents", "github", "reddit", "models", "hackernews"}


def check(name, result, expected_source_type):
    """Return a list of contract violations for one tool result."""
    problems = []

    if not isinstance(result, dict):
        return [f"returned {type(result).__name__}, expected dict"]

    text = result.get("text")
    if not isinstance(text, str) or not text.strip():
        problems.append("'text' is missing or empty")

    if result.get("source_type") != expected_source_type:
        problems.append(f"'source_type' is {result.get('source_type')!r}, expected {expected_source_type!r}")

    items = result.get("items")
    if not isinstance(items, list):
        problems.append(f"'items' is {type(items).__name__}, expected list")
        return problems

    for i, item in enumerate(items):
        if not isinstance(item, dict):
            problems.append(f"items[{i}] is {type(item).__name__}, expected dict")
            continue
        missing = [k for k in ITEM_KEYS if k not in item]
        if missing:
            problems.append(f"items[{i}] missing keys: {', '.join(missing)}")

    return problems


def main():
    failures = []

    for name, call, expected_source_type in CASES:
        print("=" * 62)
        print(f"LIVE AUDIT: {name}")
        print("=" * 62)

        try:
            result = call()
        except Exception as exc:  # a tool raising is itself the finding
            print(f"  RAISED: {type(exc).__name__}: {exc}")
            failures.append(f"{name}: raised {type(exc).__name__}")
            continue

        problems = check(name, result, expected_source_type)
        items = result.get("items", []) if isinstance(result, dict) else []

        print(f"  source_type : {result.get('source_type') if isinstance(result, dict) else '?'}")
        print(f"  items       : {len(items)}")
        for item in items[:3]:
            print(f"    - {str(item.get('title'))[:70]}")
            print(f"      {item.get('source_name')} | {item.get('date')} | {str(item.get('url'))[:70]}")
        print("  text preview:")
        text = result.get("text", "") if isinstance(result, dict) else ""
        print("    " + "\n    ".join(text.splitlines()[:6]))

        if problems:
            print("  CONTRACT VIOLATIONS:")
            for problem in problems:
                print(f"    ! {problem}")
            failures.append(f"{name}: {'; '.join(problems)}")
        elif not items:
            # Not a contract break: a live query can legitimately return nothing.
            print("  NOTE: contract OK but zero items returned (no live results, or a rate limit).")
        else:
            print("  OK")
        print()

    from agent_brain import SECTION_ORDER

    covered = {expected for _, _, expected in CASES}
    uncovered = set(SECTION_ORDER) - covered
    if uncovered:
        failures.append(f"SECTION_ORDER has untested source types: {', '.join(sorted(uncovered))}")
    unknown = covered - set(SECTION_ORDER)
    if unknown:
        failures.append(f"tests declare source types absent from SECTION_ORDER: {', '.join(sorted(unknown))}")

    print("=" * 62)
    if failures:
        print(f"FAILED — {len(failures)} contract problem(s):")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print(f"PASSED — all {len(CASES)} tools honour the dict contract, and every "
          f"SECTION_ORDER source type is covered.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
