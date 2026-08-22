import logging
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def search_news(query: str, max_results: int = 5) -> str:
    """
    Finds recent news articles on a company, product, or industry trend.
    Returns formatted observation string with explicit raw response logging.
    """
    clean_query = query.strip()
    news_list = []
    error_msg = None
    
    logger.info(f"--- [TOOL CALL] search_news(query='{clean_query}') ---")
    
    try:
        from duckduckgo_search import DDGS
        ddgs = DDGS()
        
        results = list(ddgs.news(keywords=clean_query, max_results=max_results))
        if not results:
            results = list(ddgs.text(keywords=f"{clean_query} news release", max_results=max_results))
            
        logger.info(f"[News Search Raw Response Items]: {len(results)}")
            
        for item in results:
            news_list.append({
                "title": item.get("title", "No Title"),
                "snippet": item.get("body", item.get("snippet", "No Content")),
                "url": item.get("url", item.get("href", "#")),
                "source": item.get("source", "Web News"),
                "date": item.get("date", "Recent")
            })
    except Exception as e:
        error_msg = f"Search Error: {str(e)}"
        logger.error(f"Error executing news search: {e}")

    if not news_list:
        msg = f"No results returned by Web News for query: '{clean_query}'"
        if error_msg:
            msg += f" (Error details: {error_msg})"
        logger.info(f"[TOOL RAW RESULT]: {msg}")
        return f"[News Observation]: {msg}"

    formatted_items = []
    for n in news_list:
        formatted_items.append(
            f"- Title: {n['title']} (Date: {n['date']}, Source: {n['source']})\n"
            f"  Snippet: {n['snippet']}\n"
            f"  URL: {n['url']}"
        )

    obs = f"[News Observation per Web News]: Found {len(news_list)} news articles for query '{clean_query}':\n" + "\n".join(formatted_items)
    logger.info(f"[TOOL RAW RESULT]: {obs[:300]}...")
    return obs
