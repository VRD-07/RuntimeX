import logging
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def search_news(query: str, max_results: int = 5) -> str:
    """
    Finds recent news articles on a company, product, or industry trend.
    Splits multiple competitor names cleanly (e.g. 'Tinder, Bumble' -> 'Tinder', 'Bumble').
    """
    clean_query = query.replace("Competitors:", "").replace("Track", "").strip()
    news_list = []
    
    # Split multiple competitors (e.g. "Tinder, Bumble")
    targets = [t.strip() for t in clean_query.replace(" and ", ",").split(",") if len(t.strip()) > 1]
    if not targets:
        targets = ["Dating Apps"]
        
    logger.info(f"--- [TOOL CALL] search_news(targets={targets}) ---")
    
    try:
        from duckduckgo_search import DDGS
        ddgs = DDGS()
        
        per_target_limit = max(1, max_results // len(targets))
        
        for target in targets:
            # Query each target individually for maximum search success
            search_term = f"{target} app news"
            try:
                results = list(ddgs.news(keywords=search_term, max_results=per_target_limit))
                if not results:
                    results = list(ddgs.text(keywords=f"{target} product release update", max_results=per_target_limit))
                    
                for item in results:
                    news_list.append({
                        "title": item.get("title", "No Title"),
                        "snippet": item.get("body", item.get("snippet", "No Content")),
                        "url": item.get("url", item.get("href", "#")),
                        "source": item.get("source", f"{target} News"),
                        "date": item.get("date", "Recent")
                    })
            except Exception as target_err:
                logger.warning(f"News sub-query failed for '{target}': {target_err}")
                
    except Exception as e:
        logger.error(f"Error executing news search: {e}")

    if not news_list:
        msg = f"No news articles found for query: '{clean_query}'"
        logger.info(f"[TOOL RAW RESULT]: {msg}")
        return f"[News Observation]: {msg}"

    formatted_items = []
    for n in news_list[:max_results]:
        formatted_items.append(
            f"- Title: {n['title']} (Date: {n['date']}, Source: {n['source']})\n"
            f"  Snippet: {n['snippet']}\n"
            f"  URL: {n['url']}"
        )

    obs = f"[News Observation per Web News]: Found {len(formatted_items)} news articles for '{clean_query}':\n" + "\n".join(formatted_items)
    logger.info(f"[TOOL RAW RESULT]: {obs[:300]}...")
    return obs
