import logging
import httpx
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def search_patents(query: str, max_results: int = 5) -> str:
    """
    Searches patent filings (USPTO / Google Patents) for a topic or company/inventor name.
    Filters out non-patent web homepages.
    """
    clean_query = query.replace("Competitors:", "").replace("Track", "").strip()
    words = [w for w in clean_query.split() if w.lower() not in ["and", "for", "the", "in", "recent", "trends", "research", "patents", "news", "github"]]
    target = " ".join(words[:2]) if words else "dating"
    
    logger.info(f"--- [TOOL CALL] search_patents(target='{target}') ---")
    patents = []
    
    try:
        from duckduckgo_search import DDGS
        ddgs = DDGS()
        search_term = f'"{target}" patent site:patents.google.com'
        results = list(ddgs.text(keywords=search_term, max_results=max_results * 2))
        
        for item in results:
            title = item.get("title", "").replace(" - Google Patents", "").replace(" - USPTO", "")
            snippet = item.get("body", item.get("snippet", ""))
            url = item.get("href", item.get("url", "#"))
            
            # Filter out non-patent homepages (e.g. "Tinder | Dating, Make Friends & Meet New People")
            if "Make Friends" in title or "Meet New People" in title or "Download" in title or "Official Site" in title:
                continue
                
            patents.append({
                "title": title,
                "snippet": snippet[:250],
                "url": url
            })
            if len(patents) >= max_results:
                break
    except Exception as e:
        logger.error(f"Error executing patent search: {e}")

    if not patents:
        msg = f"No patent filings found for query: '{target}'"
        logger.info(f"[TOOL RAW RESULT]: {msg}")
        return f"[PatentsView Observation]: {msg}"

    formatted_items = []
    for p in patents:
        formatted_items.append(
            f"- Title: {p['title']}\n"
            f"  Abstract/Claims Snippet: {p['snippet']}\n"
            f"  URL: {p['url']}"
        )

    obs = f"[PatentsView Observation per USPTO / Google Patents]: Found {len(patents)} patent records for query '{target}':\n" + "\n".join(formatted_items)
    logger.info(f"[TOOL RAW RESULT]: {obs[:300]}...")
    return obs
