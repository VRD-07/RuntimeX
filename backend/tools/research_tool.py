import arxiv
import httpx
import logging
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def search_semantic_scholar(query: str, max_results: int = 5) -> str:
    """
    Finds recent academic papers, citation counts, and influential works on a research topic.
    Returns formatted observation string.
    """
    clean_query = query.strip()
    papers = []
    
    # 1. Attempt Semantic Scholar Graph API
    try:
        url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={clean_query}&limit={max_results}&fields=title,authors,year,citationCount,abstract,url,venue"
        headers = {"User-Agent": "IntelPulse-Autonomous-Agent/1.0"}
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                for item in data.get("data", []):
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
    except Exception as e:
        logger.warning(f"Semantic Scholar API notice: {e}. Falling back to ArXiv API.")

    # 2. ArXiv Fallback if Semantic Scholar yields no results or times out
    if not papers:
        try:
            search = arxiv.Search(
                query=clean_query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.Relevance,
                sort_order=arxiv.SortOrder.Descending
            )
            client = arxiv.Client()
            for result in client.results(search):
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

    if not papers:
        return f"[Semantic Scholar Observation]: No academic papers found for '{clean_query}'."

    formatted_items = []
    for p in papers:
        formatted_items.append(
            f"- Title: {p['title']} ({p['year']}) | Citations: {p['citations']} | Source: {p['source']}\n"
            f"  Authors: {', '.join(p['authors'])}\n"
            f"  Abstract Snippet: {p['abstract']}...\n"
            f"  URL: {p['url']}"
        )

    return f"[Semantic Scholar Observation per {papers[0]['source']}]: Found {len(papers)} academic publications for '{clean_query}':\n" + "\n".join(formatted_items)
