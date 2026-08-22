import arxiv
import httpx
import logging
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def search_semantic_scholar(query: str, max_results: int = 5) -> str:
    """
    Finds recent academic papers, citation counts, and influential works on a research topic.
    Returns formatted observation string with explicit error logging.
    """
    clean_query = query.strip()
    papers = []
    error_msg = None
    
    logger.info(f"--- [TOOL CALL] search_semantic_scholar(query='{clean_query}') ---")
    
    # 1. Attempt Semantic Scholar Graph API
    try:
        url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={clean_query}&limit={max_results}&fields=title,authors,year,citationCount,abstract,url,venue"
        headers = {"User-Agent": "IntelPulse-Autonomous-Agent/1.0"}
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, headers=headers)
            logger.info(f"[Semantic Scholar API Status]: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                raw_items = data.get("data", [])
                logger.info(f"[Semantic Scholar Raw Response Items]: {len(raw_items)}")
                for item in raw_items:
                    papers.append({
                        "title": item.get("title"),
                        "authors": [a.get("name") for a in item.get("authors", [])[:3]],
                        "year": item.get("year", "N/A"),
                        "citations": item.get("citationCount", 0),
                        "abstract": (item.get("abstract") or "No abstract available")[:250],
                        "venue": item.get("venue", "Academic Publication"),
                        "url": item.get("url", "#"),
                        "source": "Semantic Scholar"
                    })
            else:
                error_msg = f"HTTP {response.status_code} - {response.text[:150]}"
    except Exception as e:
        error_msg = f"API Error: {str(e)}"
        logger.warning(f"Semantic Scholar API notice: {error_msg}. Falling back to ArXiv API.")

    # 2. ArXiv Fallback if Semantic Scholar yields no results or errors
    if not papers:
        try:
            search = arxiv.Search(
                query=clean_query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.Relevance,
                sort_order=arxiv.SortOrder.Descending
            )
            client = arxiv.Client()
            results = list(client.results(search))
            logger.info(f"[ArXiv Fallback Raw Response Items]: {len(results)}")
            for result in results:
                papers.append({
                    "title": result.title,
                    "authors": [a.name for a in result.authors[:3]],
                    "year": result.published.strftime("%Y") if result.published else "N/A",
                    "citations": "N/A",
                    "abstract": result.summary.replace("\n", " ")[:250],
                    "venue": "ArXiv Research",
                    "url": result.pdf_url,
                    "source": "ArXiv"
                })
        except Exception as e:
            logger.error(f"Error fetching ArXiv papers: {e}")
            if not error_msg:
                error_msg = f"ArXiv Error: {str(e)}"

    if not papers:
        msg = f"No results returned by Semantic Scholar for query: '{clean_query}'"
        if error_msg:
            msg += f" (Error details: {error_msg})"
        logger.info(f"[TOOL RAW RESULT]: {msg}")
        return f"[Semantic Scholar Observation]: {msg}"

    formatted_items = []
    for p in papers:
        formatted_items.append(
            f"- Title: {p['title']} ({p['year']}) | Citations: {p['citations']} | Source: {p['source']}\n"
            f"  Authors: {', '.join(p['authors'])}\n"
            f"  Abstract Snippet: {p['abstract']}...\n"
            f"  URL: {p['url']}"
        )

    obs = f"[Semantic Scholar Observation per {papers[0]['source']}]: Found {len(papers)} academic publications for query '{clean_query}':\n" + "\n".join(formatted_items)
    logger.info(f"[TOOL RAW RESULT]: {obs[:300]}...")
    return obs
