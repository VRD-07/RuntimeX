"""Query-coverage probe: run several real queries per tool and report item counts.

Use this to see which phrasings actually return evidence before wiring them into
an agent prompt. Tools return a dict — the LLM-facing observation is under
"text", the structured evidence under "items". Run with:

    cd backend && python test_standalone_queries.py
"""

import logging
import sys

from tools.competitor_tool import search_news
from tools.research_tool import search_semantic_scholar

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

# Live API text is not guaranteed to fit the console codec.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

NEWS_QUERIES = [
    "Sarvam AI",
    "OpenAI India",
    "Google Gemini multilingual",
    "Sarvam funding",
]

PAPER_QUERIES = [
    "multilingual NLP India",
    "low-resource language model",
    "Indic language LLM",
]


def probe(label, fn, queries):
    print("=" * 62)
    print(label)
    print("=" * 62)

    for query in queries:
        print(f"\n--- {query!r} ---")
        try:
            result = fn(query, max_results=5)
        except Exception as exc:
            print(f"  RAISED: {type(exc).__name__}: {exc}")
            continue

        items = result.get("items", [])
        print(f"  items: {len(items)}")
        for item in items:
            print(f"    - [{item.get('source_name')}] {str(item.get('title'))[:70]}")
        print("  text preview:", result.get("text", "")[:300].replace("\n", " "))


def main():
    probe("PART 1: NEWS QUERIES (search_news)", search_news, NEWS_QUERIES)
    print()
    probe("PART 2: ACADEMIC QUERIES (search_semantic_scholar)", search_semantic_scholar, PAPER_QUERIES)


if __name__ == "__main__":
    main()
