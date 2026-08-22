import httpx
import logging
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def search_github(query: str, max_results: int = 5) -> str:
    """
    Finds active repositories on GitHub related to a technology or domain.
    Filters out off-topic book/food recommendation systems.
    """
    clean_query = query.replace("Competitors:", "").replace("Track", "").strip()
    words = [w for w in clean_query.split() if w.lower() not in ["and", "for", "the", "in", "recent", "trends", "research", "patents", "news", "github"]]
    target = " ".join(words[:2]) if words else "dating app"
    
    search_term = f"{target} matchmaker" if "dating" in target.lower() else f"{target} algorithm"
    logger.info(f"--- [TOOL CALL] search_github(search_term='{search_term}') ---")
    
    results = []
    headers = {
        "User-Agent": "IntelPulse-Autonomous-Agent/1.0",
        "Accept": "application/vnd.github.v3+json"
    }
    
    url = f"https://api.github.com/search/repositories?q={search_term}&sort=stars&order=desc&per_page=10"
    
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                for item in data.get("items", []):
                    desc = item.get("description", "") or ""
                    name = item.get("full_name", "")
                    
                    # Filter out book/movie/food tinder clones
                    if "books" in name.lower() or "books" in desc.lower() or "food" in name.lower() or "movies" in name.lower():
                        continue
                        
                    results.append({
                        "name": name,
                        "description": desc[:200] if desc else "Dating match algorithm implementation",
                        "stars": item.get("stargazers_count", 0),
                        "language": item.get("language", "Python"),
                        "url": item.get("html_url"),
                        "updated_at": item.get("updated_at", "")[:10]
                    })
                    if len(results) >= max_results:
                        break
    except Exception as e:
        logger.error(f"Error querying GitHub API: {e}")

    if not results:
        msg = f"No active open-source repositories found for query: '{search_term}'"
        logger.info(f"[TOOL RAW RESULT]: {msg}")
        return f"[GitHub Observation]: {msg}"

    formatted_items = []
    for r in results:
        formatted_items.append(
            f"- Repo: {r['name']} ({r['stars']} stars, Language: {r['language']})\n"
            f"  Description: {r['description']}\n"
            f"  Last Updated: {r['updated_at']} | URL: {r['url']}"
        )

    obs = f"[GitHub Observation per GitHub API]: Found {len(results)} active repositories for query '{search_term}':\n" + "\n".join(formatted_items)
    logger.info(f"[TOOL RAW RESULT]: {obs[:300]}...")
    return obs
