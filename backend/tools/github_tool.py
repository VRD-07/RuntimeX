import httpx
import logging
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def search_github(query: str, max_results: int = 5) -> str:
    """
    Finds active repositories and recent activity on GitHub related to a technology or organization.
    Returns formatted observation string with explicit raw response logging.
    """
    clean_query = query.strip()
    results = []
    error_msg = None
    
    logger.info(f"--- [TOOL CALL] search_github(query='{clean_query}') ---")
    
    headers = {
        "User-Agent": "IntelPulse-Autonomous-Agent/1.0",
        "Accept": "application/vnd.github.v3+json"
    }
    
    url = f"https://api.github.com/search/repositories?q={clean_query}&sort=stars&order=desc&per_page={max_results}"
    
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url, headers=headers)
            logger.info(f"[GitHub API Status]: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])
                logger.info(f"[GitHub Raw Response Items]: {len(items)}")
                for item in items:
                    results.append({
                        "name": item.get("full_name"),
                        "description": item.get("description", "No description"),
                        "stars": item.get("stargazers_count", 0),
                        "language": item.get("language", "Unknown"),
                        "url": item.get("html_url"),
                        "updated_at": item.get("updated_at", "")[:10]
                    })
            else:
                error_msg = f"HTTP {response.status_code} - {response.text[:150]}"
    except Exception as e:
        error_msg = f"API Error: {str(e)}"
        logger.error(f"Error querying GitHub API: {e}")

    if not results:
        msg = f"No results returned by GitHub API for query: '{clean_query}'"
        if error_msg:
            msg += f" (Error details: {error_msg})"
        logger.info(f"[TOOL RAW RESULT]: {msg}")
        return f"[GitHub Observation]: {msg}"

    formatted_items = []
    for r in results:
        formatted_items.append(
            f"- Repo: {r['name']} ({r['stars']} stars, Language: {r['language']})\n"
            f"  Description: {r['description']}\n"
            f"  Last Updated: {r['updated_at']} | URL: {r['url']}"
        )

    obs = f"[GitHub Observation per GitHub API]: Found {len(results)} active repositories for query '{clean_query}':\n" + "\n".join(formatted_items)
    logger.info(f"[TOOL RAW RESULT]: {obs[:300]}...")
    return obs
