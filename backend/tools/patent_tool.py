import os
import logging
import httpx
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# The legacy endpoint (api.patentsview.org/patents/query) was retired by USPTO.
# The current Search API lives here and requires an API key (free, via PatentsView).
PATENTSVIEW_SEARCH_URL = "https://search.patentsview.org/api/v1/patent/"


def search_patents(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Searches patent filings for a topic or company name.

    Primary source is the PatentsView Search API, which requires PATENTSVIEW_API_KEY.
    Without a key the tool does not pretend to have queried a patent database: it falls
    back to a Google Patents web search and relabels the observation accordingly.

    Returns {"text": <observation for the LLM>, "items": [...], "source_type": "patents"}.
    """
    clean_query = query.replace("Competitors:", "").replace("Track", "").replace("patent", "").replace("patents", "").strip()
    if not clean_query:
        clean_query = "multilingual language model"

    logger.info(f"--- [TOOL CALL] search_patents(query='{clean_query}') ---")
    patents = []
    source_label = "[PatentsView API Observation]"
    item_source_name = "PatentsView (USPTO)"

    api_key = os.getenv("PATENTSVIEW_API_KEY", "").strip()

    # 1. Primary Attempt: PatentsView Search API (requires API key)
    if api_key:
        try:
            payload = {
                "q": {"_text_any": {"patent_title": clean_query}},
                "f": ["patent_id", "patent_title", "patent_date", "patent_abstract"],
                "o": {"size": max_results},
            }
            with httpx.Client(timeout=10.0) as client:
                res = client.post(
                    PATENTSVIEW_SEARCH_URL,
                    json=payload,
                    headers={"X-Api-Key": api_key, "Accept": "application/json"},
                    follow_redirects=True,
                )
                logger.info(f"[PatentsView Raw API Status]: HTTP {res.status_code}")

                if res.status_code == 200 and "json" in res.headers.get("content-type", "").lower():
                    data = res.json()
                    for item in data.get("patents", []) or []:
                        pat_id = item.get("patent_id")
                        patents.append({
                            "title": item.get("patent_title") or "Patent Document",
                            "number": pat_id or "N/A",
                            "date": item.get("patent_date") or "N/A",
                            "snippet": (item.get("patent_abstract") or "Abstract not available")[:250],
                            "url": f"https://patents.google.com/patent/US{pat_id}/en" if pat_id else "#",
                        })
                else:
                    logger.warning(f"[PatentsView API Error]: HTTP {res.status_code} - {res.text[:200]}")
        except Exception as e:
            logger.warning(f"[PatentsView API attempt failed]: {e}")
    else:
        logger.info("[Patents Tool]: PATENTSVIEW_API_KEY not set — skipping PatentsView API and using web fallback.")

    # 2. Fallback Attempt: Google Patents web search (explicitly relabeled)
    if not patents:
        source_label = "[Google Patents Observation (web search fallback, NOT a verified PatentsView database query)]"
        item_source_name = "Google Patents (web search)"
        logger.info(f"[Patents Tool]: Executing Google Patents web search for query: '{clean_query}'.")

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
                if any(bad in title_lower for bad in ["merriam-webster", "wikipedia", "dictionary", "forum", "bbs", "blog"]):
                    continue

                # Only accept results that actually live on Google Patents
                if "patents.google.com" not in url:
                    continue

                patents.append({
                    "title": title,
                    "number": "Patent Filing",
                    "date": "Recent",
                    "snippet": snippet[:250],
                    "url": url,
                })
                if len(patents) >= max_results:
                    break
        except Exception as fallback_err:
            logger.error(f"Error in Google Patents fallback search: {fallback_err}")

    # 3. Honest Empty Result Handling
    if not patents:
        msg = f"No verified patent filings found for query: '{clean_query}'"
        logger.info(f"[TOOL RAW RESULT]: {msg}")
        return {
            "text": f"{source_label}: {msg}",
            "items": [],
            "source_type": "patents",
        }

    formatted_items = []
    for p in patents:
        formatted_items.append(
            f"- Title: {p['title']} (Patent: {p['number']}, Date: {p['date']})\n"
            f"  Abstract/Claims Snippet: {p['snippet']}\n"
            f"  URL: {p['url']}"
        )

    obs = f"{source_label}: Found {len(patents)} patent records for query '{clean_query}':\n" + "\n".join(formatted_items)
    logger.info(f"[TOOL RAW RESULT]: {obs[:300]}...")

    items = [
        {
            "title": p["title"],
            "snippet": p["snippet"],
            "source_name": item_source_name,
            "date": p["date"],
            "url": p["url"],
        }
        for p in patents
    ]
    return {"text": obs, "items": items, "source_type": "patents"}
