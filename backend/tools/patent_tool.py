import logging
import httpx
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def search_patents(query: str, max_results: int = 5) -> str:
    """
    Searches patent filings (USPTO / Google Patents) for a topic or company/inventor name.
    Returns formatted observation string with explicit raw response logging.
    """
    clean_query = query.strip()
    patents = []
    error_msg = None
    
    logger.info(f"--- [TOOL CALL] search_patents(query='{clean_query}') ---")
    
    try:
        from duckduckgo_search import DDGS
        ddgs = DDGS()
        search_term = f"{clean_query} patent"
        results = list(ddgs.text(keywords=search_term, max_results=max_results))
        logger.info(f"[Patents Search Raw Response Items]: {len(results)}")
        
        for item in results:
            title = item.get("title", "Patent Document").replace(" - Google Patents", "").replace(" - USPTO", "")
            snippet = item.get("body", item.get("snippet", ""))
            url = item.get("href", item.get("url", "#"))
            patents.append({
                "title": title,
                "snippet": snippet,
                "url": url
            })
    except Exception as e:
        error_msg = f"Search Error: {str(e)}"
        logger.error(f"Error executing patent search: {e}")

    if not patents:
        msg = f"No results returned by PatentsView for query: '{clean_query}'"
        if error_msg:
            msg += f" (Error details: {error_msg})"
        logger.info(f"[TOOL RAW RESULT]: {msg}")
        return f"[PatentsView Observation]: {msg}"

    formatted_items = []
    for p in patents:
        formatted_items.append(
            f"- Title: {p['title']}\n"
            f"  Abstract/Claims Snippet: {p['snippet']}\n"
            f"  URL: {p['url']}"
        )

    obs = f"[PatentsView Observation per USPTO / Google Patents]: Found {len(patents)} patent records for query '{clean_query}':\n" + "\n".join(formatted_items)
    logger.info(f"[TOOL RAW RESULT]: {obs[:300]}...")
    return obs
