import re
import html
import httpx
import logging
import urllib.parse
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

def search_reddit(query: str, subreddit: Optional[str] = None, max_results: int = 5) -> Dict[str, Any]:
    """
    Searches recent Reddit posts matching the query, optionally scoped to a subreddit.
    Returns post title, subreddit, snippet, permalink, and date — real community sentiment on competitors.

    Returns {"text": <observation for the LLM>, "items": [...], "source_type": "reddit"}.
    Item URLs are the permalinks from the Reddit RSS feed.

    The request is pinned to type=link because Reddit's unfiltered search feed
    mixes subreddit records (id t5_*) in with posts (id t3_*); a subreddit
    listing carries no author, no discussion and no <category>, so surfacing it
    as a "community post" would misrepresent it. Entries are re-checked against
    the t3_ prefix in case the parameter is ever ignored.
    """
    clean_query = query.replace("Competitors:", "").replace("Track", "").strip()
    words = [w for w in clean_query.split() if w.lower() not in ["and", "for", "the", "in", "recent", "trends", "research", "patents", "news", "github", "reddit"]]
    target = " ".join(words[:3]) if words else "language model"

    encoded_target = urllib.parse.quote_plus(target)
    if subreddit and subreddit.strip():
        sub_name = subreddit.strip().replace("r/", "")
        endpoint = f"https://www.reddit.com/r/{sub_name}/search.rss?q={encoded_target}&sort=new&restrict_sr=on&type=link"
    else:
        endpoint = f"https://www.reddit.com/search.rss?q={encoded_target}&sort=new&type=link"

    logger.info(f"--- [TOOL CALL] search_reddit(target='{target}', subreddit='{subreddit}') ---")

    results = []
    rate_limited = False
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(endpoint, headers=headers, follow_redirects=True)
            logger.info(f"[Reddit Raw Feed Status]: HTTP {resp.status_code}")
            if resp.status_code == 200:
                raw_xml = resp.text
                entries = re.findall(r'<entry>(.*?)</entry>', raw_xml, re.DOTALL)
                logger.info(f"[Reddit Raw Feed Entries]: {len(entries)} entries for target '{target}'")

                for entry in entries:
                    # Keep posts only. t3_ = link/post, t5_ = subreddit.
                    id_m = re.search(r'<id>(.*?)</id>', entry)
                    if id_m and not id_m.group(1).strip().startswith("t3_"):
                        continue

                    # Title
                    title_m = re.search(r'<title>(.*?)</title>', entry)
                    title = html.unescape(title_m.group(1)).strip() if title_m else "Reddit Post"

                    # Link / Permalink
                    link_m = re.search(r'<link href="(.*?)"', entry)
                    url = link_m.group(1) if link_m else "https://reddit.com"

                    # Subreddit: prefer the feed's own category, otherwise read it
                    # off the permalink. Never invent a placeholder.
                    sub_m = re.search(r'<category term="(.*?)"', entry)
                    sub = html.unescape(sub_m.group(1)).strip() if sub_m else ""
                    if not sub:
                        path_m = re.search(r'reddit\.com/r/([^/]+)/', url)
                        sub = path_m.group(1) if path_m else ""
                    if sub and not sub.startswith(("r/", "u/", "u_")):
                        sub = f"r/{sub}"
                    source_name = sub or "Reddit"

                    # Date
                    date_m = re.search(r'<updated>(.*?)</updated>', entry)
                    date_str = date_m.group(1)[:10] if date_m else "Recent"

                    # Snippet from content
                    content_m = re.search(r'<content type="html">(.*?)</content>', entry, re.DOTALL)
                    snippet = "Community discussion and user feedback."
                    if content_m:
                        raw_content = html.unescape(content_m.group(1))
                        # Strip HTML tags
                        clean_text = re.sub(r'<[^>]+>', ' ', raw_content)
                        clean_text = ' '.join(clean_text.split())
                        if len(clean_text) > 20:
                            snippet = clean_text[:250]

                    results.append({
                        "title": title,
                        "subreddit": source_name,
                        "snippet": snippet,
                        "url": url,
                        "date": date_str
                    })

                    if len(results) >= max_results:
                        break
            else:
                # Reddit rate-limits anonymous RSS aggressively. Reporting this as
                # "no posts found" would read as an absence of community interest.
                rate_limited = resp.status_code == 429
                logger.warning(f"Reddit RSS returned HTTP {resp.status_code} for target '{target}'")
    except Exception as e:
        logger.error(f"Error querying Reddit API: {e}")

    if not results:
        if rate_limited:
            msg = f"Reddit rate-limited this request (HTTP 429); community coverage for '{target}' is unavailable, not empty"
        else:
            msg = f"No recent Reddit community posts found for query: '{target}'"
        logger.info(f"[TOOL RAW RESULT]: {msg}")
        return {
            "text": f"[Reddit Observation]: {msg}",
            "items": [],
            "source_type": "reddit",
        }

    formatted_items = []
    for r in results:
        formatted_items.append(
            f"- Title: {r['title']} (Subreddit: {r['subreddit']}, Date: {r['date']})\n"
            f"  User Snippet: {r['snippet']}\n"
            f"  URL: {r['url']}"
        )

    obs = f"[Reddit Observation per Reddit RSS]: Found {len(results)} community posts for query '{target}':\n" + "\n".join(formatted_items)
    logger.info(f"[TOOL RAW RESULT]: {obs[:300]}...")

    items = [
        {
            "title": r["title"],
            "snippet": r["snippet"],
            "source_name": r["subreddit"],
            "date": r["date"],
            "url": r["url"],
        }
        for r in results
    ]
    return {"text": obs, "items": items, "source_type": "reddit"}
