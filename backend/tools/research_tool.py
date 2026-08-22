import arxiv
import httpx
import logging
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Irrelevant domains to filter out
EXCLUDED_KEYWORDS = ["covid", "contact tracing", "epidemic", "neutron", "kilonova", "astrophysics", "cell biology"]

def search_semantic_scholar(query: str, max_results: int = 5) -> str:
    """
    Finds recent academic papers strictly relevant to the research domain.
    Filters out off-topic papers like COVID contact tracing.
    """
    clean_query = query.replace("Competitors:", "").replace("Track", "").strip()
    # Form concise 2-3 word search query
    words = [w for w in clean_query.split() if w.lower() not in ["and", "for", "the", "in", "recent", "trends", "research", "patents", "news", "github"]]
    focused_query = " ".join(words[:3]) if words else "dating app matching"
    
    logger.info(f"--- [TOOL CALL] search_semantic_scholar(focused_query='{focused_query}') ---")
    papers = []
    
    # 1. Semantic Scholar API Call
    try:
        url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={focused_query}&limit=10&fields=title,authors,year,citationCount,abstract,url,venue"
        headers = {"User-Agent": "IntelPulse-Autonomous-Agent/1.0"}
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                for item in data.get("data", []):
                    title = item.get("title", "")
                    abstract = item.get("abstract", "") or ""
                    
                    # Filter out excluded topics
                    if any(ex in title.lower() or ex in abstract.lower() for ex in EXCLUDED_KEYWORDS):
                        continue
                        
                    papers.append({
                        "title": title,
                        "authors": [a.get("name") for a in item.get("authors", [])[:3]],
                        "year": item.get("year", "N/A"),
                        "citations": item.get("citationCount", 0),
                        "abstract": abstract[:250],
                        "venue": item.get("venue", "Academic Publication"),
                        "url": item.get("url", "#"),
                        "source": "Semantic Scholar"
                    })
                    if len(papers) >= max_results:
                        break
    except Exception as e:
        logger.warning(f"Semantic Scholar API notice: {e}. Falling back to ArXiv.")

    # 2. ArXiv Fallback with strict relevance filtering
    if not papers:
        try:
            search = arxiv.Search(
                query=f'all:"{focused_query}"',
                max_results=20,
                sort_by=arxiv.SortCriterion.Relevance,
                sort_order=arxiv.SortOrder.Descending
            )
            client = arxiv.Client()
            for result in client.results(search):
                title = result.title
                summary = result.summary.replace("\n", " ")
                
                if any(ex in title.lower() or ex in summary.lower() for ex in EXCLUDED_KEYWORDS):
                    continue
                    
                papers.append({
                    "title": title,
                    "authors": [a.name for a in result.authors[:3]],
                    "year": result.published.strftime("%Y") if result.published else "N/A",
                    "citations": "N/A",
                    "abstract": summary[:250],
                    "venue": "ArXiv Research",
                    "url": result.pdf_url,
                    "source": "ArXiv"
                })
                if len(papers) >= max_results:
                    break
        except Exception as e:
            logger.error(f"Error fetching ArXiv papers: {e}")

    if not papers:
        msg = f"No academic papers found for query: '{focused_query}'"
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

    obs = f"[Semantic Scholar Observation per {papers[0]['source']}]: Found {len(papers)} academic publications for query '{focused_query}':\n" + "\n".join(formatted_items)
    logger.info(f"[TOOL RAW RESULT]: {obs[:300]}...")
    return obs
