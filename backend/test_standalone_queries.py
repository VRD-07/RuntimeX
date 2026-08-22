import sys
import logging

from tools.competitor_tool import search_news
from tools.research_tool import search_semantic_scholar

logging.basicConfig(level=logging.INFO)

print("==================================================")
print("PART 1: TESTING NEWS QUERIES (search_news)")
print("==================================================")

news_queries = [
    "Sarvam AI",
    "OpenAI India",
    "Google Gemini multilingual",
    "Sarvam funding"
]

for q in news_queries:
    print(f"\n--- TESTING search_news('{q}') ---")
    res = search_news(q, max_results=5)
    print("Result snippet:\n", res[:400])

print("\n==================================================")
print("PART 2: TESTING ACADEMIC QUERIES (search_semantic_scholar)")
print("==================================================")

paper_queries = [
    "multilingual NLP India",
    "low-resource language model",
    "Indic language LLM"
]

for q in paper_queries:
    print(f"\n--- TESTING search_semantic_scholar('{q}') ---")
    res = search_semantic_scholar(q, max_results=5)
    print("Result snippet:\n", res[:400])
