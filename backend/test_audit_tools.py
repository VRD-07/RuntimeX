import logging
from tools.competitor_tool import search_news
from tools.research_tool import search_semantic_scholar

logging.basicConfig(level=logging.INFO)

print("==================================================")
print("LIVE AUDIT TEST 1: search_news('Sarvam AI')")
print("==================================================")
res_news = search_news("Sarvam AI", max_results=5)
print("\n--- OUTPUT FOR search_news ---")
print(res_news)

print("\n==================================================")
print("LIVE AUDIT TEST 2: search_semantic_scholar('low-resource language model')")
print("==================================================")
res_scholar = search_semantic_scholar("low-resource language model", max_results=5)
print("\n--- OUTPUT FOR search_semantic_scholar ---")
print(res_scholar)
