import logging
import httpx
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def search_patents(query: str, max_results: int = 5) -> str:
    """
    Searches patent filings for a topic or company name.
    Logs raw API responses, uses exact input query parameter,
    and explicitly relabels any web fallback so PatentsView is never falsely claimed.
    """
    clean_query = query.replace("Competitors:", "").replace("Track", "").replace("patent", "").replace("patents", "").strip()
    if not clean_query:
        clean_query = "multilingual language model"

    logger.info(f"--- [TOOL CALL] search_patents(query='{clean_query}') ---")
    patents = []
    source_label = "[PatentsView API Observation]"

    # 1. Primary Attempt: PatentsView API
    try:
        pv_url = "https://api.patentsview.org/patents/query"
        payload = {
            "q": {"_text_any": {"patent_title": clean_query}},
            "f": ["patent_number", "patent_title", "patent_date", "patent_abstract"],
            "o": {"per_page": max_results}
        }
        with httpx.Client(timeout=8.0) as client:
            res = client.post(pv_url, json=payload, follow_redirects=True)
            logger.info(f"[Patents Raw API Response]: HTTP {res.status_code} - Body: {res.text[:400]}")
            
            if res.status_code == 200 and res.headers.get("content-type", "").startswith("application/json"):
                data = res.json()
                pv_items = data.get("patents", [])
                for item in pv_items:
                    patents.append({
                        "title": item.get("patent_title", "Patent Document"),
                        "number": item.get("patent_number", "N/A"),
                        "date": item.get("patent_date", "N/A"),
                        "snippet": (item.get("patent_abstract") or "Abstract not available")[:250],
                        "url": f"https://patents.google.com/patent/US{item.get('patent_number')}/en" if item.get('patent_number') else "#"
                    })
    except Exception as e:
        logger.warning(f"PatentsView API attempt notice: {e}")

    # 2. Fallback Attempt: Google Patents Search (Explicitly Relabeled)
    if not patents:
        source_label = "[Google Patents Observation (Web fallback, NOT a verified PatentsView database)]"
        logger.info(f"[Patents Tool]: PatentsView API returned 0 items. Executing Google Patents web search for query: '{clean_query}'.")
        
        try:
            from duckduckgo_search import DDGS
            ddgs = DDGS()
            search_term = f'"{clean_query}" patent site:patents.google.com'
            logger.info(f"[Google Patents Fallback Search Term]: {search_term}")
            
            results = list(ddgs.text(keywords=search_term, max_results=max_results * 2))
            logger.info(f"[Google Patents Raw Fallback Items Count]: {len(results)}")
            
            for item in results:
                title = item.get("title", "").replace(" - Google Patents", "").replace(" - USPTO", "").strip()
                snippet = item.get("body", item.get("snippet", "")).strip()
                url = item.get("href", item.get("url", "#"))
                
                title_lower = title.lower()
                snippet_lower = snippet.lower()
                
                # Exclude dictionary entries, general blogs, forums, and non-patents
                if any(bad in title_lower for bad in ["merriam-webster", "wikipedia", "dictionary", "forum", "bbs", "blog", "make friends", "meet new people"]):
                    continue
                    
                # Require genuine patent indicator or URL from patents.google.com
                if "patents.google.com" in url or "patent" in title_lower or "patent" in snippet_lower or "method" in title_lower or "system" in title_lower or "apparatus" in title_lower or "us" in title_lower:
                    patents.append({
                        "title": title,
                        "number": "Patent Filing",
                        "date": "Recent",
                        "snippet": snippet[:250],
                        "url": url
                    })
                    if len(patents) >= max_results:
                        break
        except Exception as fallback_err:
            logger.error(f"Error in Google Patents fallback search: {fallback_err}")

    # 3. Honest Empty Result Handling
    if not patents:
        msg = f"No verified patent filings found for query: '{clean_query}'"
        logger.info(f"[TOOL RAW RESULT]: {msg}")
        return f"{source_label}: {msg}"

    formatted_items = []
    for p in patents:
        formatted_items.append(
            f"- Title: {p['title']}\n"
            f"  Abstract/Claims Snippet: {p['snippet']}\n"
            f"  URL: {p['url']}"
        )

    obs = f"{source_label}: Found {len(patents)} patent records for query '{clean_query}':\n" + "\n".join(formatted_items)
    logger.info(f"[TOOL RAW RESULT]: {obs[:300]}...")
    return obs
