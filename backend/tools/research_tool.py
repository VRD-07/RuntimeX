import os
import time
import httpx
import logging
import urllib.parse
import xml.etree.ElementTree as ET
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# Irrelevant domains to filter out
EXCLUDED_KEYWORDS = ["covid", "contact tracing", "epidemic", "neutron", "kilonova", "astrophysics", "cell biology"]

def search_semantic_scholar(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Finds recent academic papers using official academic APIs.
    Calls Semantic Scholar Graph API as primary source; if HTTP 429 is hit, falls back to ArXiv API with explicit relabeling.
    Prints literal request URL before execution and includes retry-with-backoff.

    Returns {"text": <observation for the LLM>, "items": [...], "source_type": "research"}.
    Item URLs come straight from the upstream API.
    """
    clean_query = query.replace("Competitors:", "").replace("Track", "").replace("research", "").replace("papers", "").strip()
    if not clean_query:
        clean_query = "multilingual language model"

    words = [w for w in clean_query.split() if w.lower() not in ["and", "for", "the", "in", "recent", "trends", "research"]]
    focused_query = " ".join(words[:4]) if words else "multilingual language model"

    encoded_query = urllib.parse.quote(focused_query)
    ss_url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={encoded_query}&limit={max_results*2}&fields=title,abstract,year,citationCount,url,authors"

    logger.info(f"--- [TOOL CALL] search_semantic_scholar(query='{clean_query}') ---")
    logger.info(f"[Semantic Scholar API Call]: Executing request URL: '{ss_url}'")

    headers = {
        "User-Agent": "IntelPulse-Autonomous-Agent/1.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json"
    }
    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip()
    if api_key:
        headers["x-api-key"] = api_key

    papers = []
    source_label = "[Semantic Scholar Observation per Semantic Scholar Graph API]"
    api_source_name = "Semantic Scholar"
    ss_response = None

    # 1. Primary Attempt: Semantic Scholar Graph API (with 1 retry)
    for attempt in range(2):
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(ss_url, headers=headers)
                logger.info(f"[Semantic Scholar API Raw Status]: HTTP {res.status_code} (Attempt {attempt+1})")
                if res.status_code == 200:
                    ss_response = res
                    break
                elif res.status_code in [429, 500, 502, 503] and attempt == 0:
                    logger.warning(f"[Semantic Scholar API Retry]: Received HTTP {res.status_code}. Retrying in 1.5s...")
                    time.sleep(1.5)
                else:
                    logger.error(f"[Semantic Scholar API Error]: HTTP {res.status_code} - Body: {res.text[:200]}")
                    break
        except Exception as e:
            if attempt == 0:
                logger.warning(f"[Semantic Scholar Exception]: {e}. Retrying in 1.5s...")
                time.sleep(1.5)
            else:
                logger.error(f"[Semantic Scholar Exception Failed]: {e}")

    # Process Semantic Scholar Graph API Response
    if ss_response and ss_response.status_code == 200:
        try:
            data = ss_response.json()
            items = data.get("data", [])
            logger.info(f"[Semantic Scholar Raw Items Count]: {len(items)} items returned")

            for item in items:
                title = item.get("title", "").strip()
                abstract = (item.get("abstract") or "Abstract not provided in database").strip()
                
                if any(ex in title.lower() or ex in abstract.lower() for ex in EXCLUDED_KEYWORDS):
                    continue

                authors_list = [a.get("name") for a in item.get("authors", [])[:3] if a.get("name")]
                authors_str = ", ".join(authors_list) if authors_list else "Academic Authors"
                year_str = str(item.get("year")) if item.get("year") else "Recent"
                citations_str = str(item.get("citationCount")) if item.get("citationCount") is not None else "N/A"
                url_str = item.get("url") or "#"

                if title:
                    papers.append({
                        "title": title,
                        "authors": authors_str,
                        "year": year_str,
                        "citations": citations_str,
                        "abstract": abstract[:250],
                        "url": url_str
                    })
                    if len(papers) >= max_results:
                        break
        except Exception as json_err:
            logger.error(f"Error parsing Semantic Scholar JSON response: {json_err}")

    # 2. Fallback Attempt: ArXiv API (Explicitly Relabeled)
    if not papers:
        source_label = "[ArXiv Research API Observation (Fallback from Semantic Scholar)]"
        api_source_name = "arXiv"
        arxiv_url = f"https://export.arxiv.org/api/query?search_query=all:{encoded_query}&max_results={max_results*2}"
        logger.info(f"[ArXiv Fallback API Call]: Executing request URL: '{arxiv_url}'")
        
        try:
            with httpx.Client(timeout=12.0) as client:
                res = client.get(arxiv_url, headers=headers, follow_redirects=True)
                logger.info(f"[ArXiv API Raw Status]: HTTP {res.status_code}")
                
                if res.status_code == 200:
                    root = ET.fromstring(res.text)
                    ns = {'atom': 'http://www.w3.org/2005/Atom'}
                    entries = root.findall('atom:entry', ns)
                    logger.info(f"[ArXiv Raw Items Count]: {len(entries)} items returned")

                    for entry in entries:
                        raw_title = entry.find('atom:title', ns).text if entry.find('atom:title', ns) is not None else ""
                        raw_summary = entry.find('atom:summary', ns).text if entry.find('atom:summary', ns) is not None else ""
                        pub_elem = entry.find('atom:published', ns)
                        year_str = pub_elem.text[:4] if pub_elem is not None else "Recent"
                        pdf_elem = entry.find('atom:id', ns)
                        url_str = pdf_elem.text if pdf_elem is not None else "#"

                        # Extract authors
                        author_elems = entry.findall('atom:author', ns)
                        authors_list = [a.find('atom:name', ns).text for a in author_elems[:3] if a.find('atom:name', ns) is not None]
                        authors_str = ", ".join(authors_list) if authors_list else "ArXiv Authors"

                        title = ' '.join(raw_title.split())
                        abstract = ' '.join(raw_summary.split())

                        if any(ex in title.lower() or ex in abstract.lower() for ex in EXCLUDED_KEYWORDS):
                            continue

                        if title:
                            papers.append({
                                "title": title,
                                "authors": authors_str,
                                "year": year_str,
                                "citations": "N/A",
                                "abstract": abstract[:250],
                                "url": url_str
                            })
                            if len(papers) >= max_results:
                                break
        except Exception as arxiv_err:
            logger.error(f"Error querying ArXiv API: {arxiv_err}")

    # 3. Honest Empty Result Handling
    if not papers:
        msg = f"No academic publications found for query: '{clean_query}'"
        logger.info(f"[TOOL RAW RESULT]: {msg}")
        return {
            "text": f"{source_label}: {msg}",
            "items": [],
            "source_type": "research",
        }

    formatted_items = []
    for p in papers:
        formatted_items.append(
            f"- Title: {p['title']} ({p['year']}) | Citations: {p['citations']}\n"
            f"  Authors: {p['authors']}\n"
            f"  Abstract Snippet: {p['abstract']}...\n"
            f"  URL: {p['url']}"
        )

    obs = f"{source_label}: Found {len(papers)} publications for query '{clean_query}':\n" + "\n".join(formatted_items)
    logger.info(f"[TOOL RAW RESULT]: {obs[:300]}...")

    items = [
        {
            "title": p["title"],
            "snippet": p["abstract"],
            "source_name": f"{api_source_name} ({p['citations']} citations)" if p["citations"] != "N/A" else api_source_name,
            "date": p["year"],
            "url": p["url"],
        }
        for p in papers
    ]
    return {"text": obs, "items": items, "source_type": "research"}
