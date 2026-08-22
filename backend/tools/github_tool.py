import httpx
import logging
import urllib.parse
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

def search_github(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Finds active repositories on GitHub related to a technology or domain.
    Directly passes the exact input query parameter into the GitHub REST API request URL.
    Logs exact query strings right before the API call to confirm dynamic execution.

    Returns {"text": <observation for the LLM>, "items": [...], "source_type": "github"}.
    Item URLs are the html_url values returned by the GitHub API.
    """
    clean_query = query.replace("Competitors:", "").replace("Track", "").replace("github", "").replace("repositories", "").strip()
    if not clean_query:
        clean_query = "multilingual language model"

    # Encode query string cleanly for API request URL
    encoded_query = urllib.parse.quote(clean_query)
    url = f"https://api.github.com/search/repositories?q={encoded_query}&sort=stars&order=desc&per_page=10"

    logger.info(f"--- [TOOL CALL] search_github(query='{clean_query}') ---")
    logger.info(f"[GitHub API Call]: Executing search for query='{clean_query}', Request URL='{url}'")

    results = []
    headers = {
        "User-Agent": "IntelPulse-Autonomous-Agent/1.0",
        "Accept": "application/vnd.github.v3+json"
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url, headers=headers)
            logger.info(f"[GitHub Raw API Status]: HTTP {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])
                logger.info(f"[GitHub Raw API Items Count]: {len(items)} items returned for query '{clean_query}'")
                
                for item in items:
                    desc = item.get("description", "") or ""
                    name = item.get("full_name", "")

                    results.append({
                        "name": name,
                        "description": desc[:200] if desc else "Repository description not provided",
                        "stars": item.get("stargazers_count", 0),
                        # Forks, open issues and pushed_at are the engineering-velocity
                        # signals: stars measure past attention, these measure whether
                        # the project is being built on and maintained right now.
                        "forks": item.get("forks_count", 0),
                        "open_issues": item.get("open_issues_count", 0),
                        "owner": (item.get("owner") or {}).get("login") or "",
                        "license": ((item.get("license") or {}).get("spdx_id") or "").replace("NOASSERTION", ""),
                        "topics": [t for t in (item.get("topics") or []) if isinstance(t, str)][:5],
                        "language": item.get("language") or "Code",
                        "url": item.get("html_url", "#"),
                        "created_at": (item.get("created_at") or "")[:10],
                        "pushed_at": (item.get("pushed_at") or "")[:10],
                        "updated_at": item.get("updated_at", "")[:10] if item.get("updated_at") else "Recent"
                    })
                    if len(results) >= max_results:
                        break
            else:
                logger.warning(f"GitHub API returned HTTP {response.status_code}: {response.text[:200]}")
    except Exception as e:
        logger.error(f"Error querying GitHub API for query '{clean_query}': {e}")

    if not results:
        msg = f"No active open-source repositories found for query: '{clean_query}'"
        logger.info(f"[TOOL RAW RESULT]: {msg}")
        return {
            "text": f"[GitHub Observation]: {msg}",
            "items": [],
            "source_type": "github",
        }

    formatted_items = []
    for r in results:
        formatted_items.append(
            f"- Repo: {r['name']} ({r['stars']} stars, {r['forks']} forks, "
            f"{r['open_issues']} open issues, Language: {r['language']})\n"
            f"  Description: {r['description']}\n"
            f"  Created: {r['created_at'] or 'unknown'} | Last push: {r['pushed_at'] or 'unknown'} | URL: {r['url']}"
        )

    obs = f"[GitHub Observation per GitHub API]: Found {len(results)} active repositories for query '{clean_query}':\n" + "\n".join(formatted_items)
    logger.info(f"[TOOL RAW RESULT]: {obs[:300]}...")

    items = []
    for r in results:
        detail = [r["description"]]
        signals = [f"{r['forks']} forks", f"{r['open_issues']} open issues"]
        if r["pushed_at"]:
            signals.append(f"last push {r['pushed_at']}")
        if r["license"]:
            signals.append(f"license {r['license']}")
        if r["topics"]:
            signals.append("topics: " + ", ".join(r["topics"]))
        detail.append(" | ".join(signals))

        items.append({
            "title": r["name"],
            "snippet": ". ".join(p for p in detail if p)[:400],
            # ASCII only: this string reaches the log stream, and a Windows
            # cp1252 console raises UnicodeEncodeError on glyphs like U+2605.
            "source_name": f"GitHub | {r['stars']} stars | {r['forks']} forks | {r['language']}",
            "date": r["pushed_at"] or r["updated_at"],
            "url": r["url"],
        })
    return {"text": obs, "items": items, "source_type": "github"}
