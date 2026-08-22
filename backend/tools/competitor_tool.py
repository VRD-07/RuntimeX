import logging
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def search_news(query: str, max_results: int = 5) -> str:
    """
    Finds recent news articles on a company, product, or industry trend.
    Returns formatted observation string.
    """
    clean_query = query.strip()
    news_list = []
    
    try:
        from duckduckgo_search import DDGS
        ddgs = DDGS()
        
        results = list(ddgs.news(keywords=clean_query, max_results=max_results))
        if not results:
            results = list(ddgs.text(keywords=f"{clean_query} news release", max_results=max_results))
            
        for item in results:
            news_list.append({
                "title": item.get("title", "No Title"),
                "snippet": item.get("body", item.get("snippet", "No Content")),
                "url": item.get("url", item.get("href", "#")),
                "source": item.get("source", "Web News"),
                "date": item.get("date", "Recent")
            })
    except Exception as e:
        logger.error(f"Error executing news search: {e}")

    if not news_list:
        return f"[News Observation]: No news articles found for '{clean_query}'."

    formatted_items = []
    for n in news_list:
        formatted_items.append(
            f"- Title: {n['title']} (Date: {n['date']}, Source: {n['source']})\n"
            f"  Snippet: {n['snippet']}\n"
            f"  URL: {n['url']}"
        )

    return f"[News Observation per Web News]: Found {len(news_list)} news articles for '{clean_query}':\n" + "\n".join(formatted_items)
