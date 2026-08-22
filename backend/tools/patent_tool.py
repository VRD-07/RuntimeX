import logging
import httpx
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def search_patents(query: str, max_results: int = 5) -> str:
    """
    Searches patent filings (USPTO / Google Patents) for a topic or company/inventor name.
    Returns formatted observation string.
    """
    clean_query = query.strip()
    patents = []
    
    # Try querying USPTO PatentsView API or DuckDuckGo patent search
    try:
        from duckduckgo_search import DDGS
        ddgs = DDGS()
        search_term = f"{clean_query} site:patents.google.com OR site:uspto.gov patent"
        results = list(ddgs.text(keywords=search_term, max_results=max_results))
        
        for item in results:
            title = item.get("title", "Patent Document").replace(" - Google Patents", "")
            snippet = item.get("body", item.get("snippet", ""))
            url = item.get("href", item.get("url", "#"))
            patents.append({
                "title": title,
                "snippet": snippet,
                "url": url
            })
    except Exception as e:
        logger.error(f"Error executing patent search: {e}")

    if not patents:
        return f"[PatentsView Observation]: No public patent filings found matching '{clean_query}'."

    formatted_items = []
    for p in patents:
        formatted_items.append(
            f"- Title: {p['title']}\n"
            f"  Abstract/Claims: {p['snippet']}\n"
            f"  URL: {p['url']}"
        )

    return f"[PatentsView Observation per USPTO / Google Patents]: Found {len(patents)} patent records for '{clean_query}':\n" + "\n".join(formatted_items)
