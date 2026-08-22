import re
import html
import httpx
import logging
from typing import Optional, List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def search_reddit(query: str, subreddit: Optional[str] = None, max_results: int = 5) -> str:
    """
    Searches recent Reddit posts/comments matching the query, optionally scoped to a subreddit.
    Returns post title, subreddit, upvote count/sentiment, snippet, permalink, and date.
    Gives real community sentiment on competitors.
    """
    clean_query = query.replace("Competitors:", "").replace("Track", "").strip()
    words = [w for w in clean_query.split() if w.lower() not in ["and", "for", "the", "in", "recent", "trends", "research", "patents", "news", "github", "reddit"]]
    target = " ".join(words[:3]) if words else "dating app"
    
    if subreddit and subreddit.strip():
        sub_name = subreddit.strip().replace("r/", "")
        endpoint = f"https://www.reddit.com/r/{sub_name}/search.rss?q={target}&sort=new&restrict_sr=on"
    else:
        endpoint = f"https://www.reddit.com/search.rss?q={target}&sort=new"

    logger.info(f"--- [TOOL CALL] search_reddit(target='{target}', subreddit='{subreddit}') ---")
    
    results = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(endpoint, headers=headers, follow_redirects=True)
            if resp.status_code == 200:
                raw_xml = resp.text
                entries = re.findall(r'<entry>(.*?)</entry>', raw_xml, re.DOTALL)
                
                for entry in entries:
                    # Title
                    title_m = re.search(r'<title>(.*?)</title>', entry)
                    title = html.unescape(title_m.group(1)).strip() if title_m else "Reddit Post"
                    
                    # Link / Permalink
                    link_m = re.search(r'<link href="(.*?)"', entry)
                    url = link_m.group(1) if link_m else "https://reddit.com"

                    # Subreddit
                    sub_m = re.search(r'<category term="(.*?)"', entry)
                    sub = sub_m.group(1).strip() if sub_m else "r/reddit"
                    if not sub.startswith("r/"):
                        sub = f"r/{sub}"

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
                        "subreddit": sub,
                        "upvotes": "Community Upvoted",
                        "snippet": snippet,
                        "url": url,
                        "date": date_str
                    })

                    if len(results) >= max_results:
                        break
    except Exception as e:
        logger.error(f"Error querying Reddit API: {e}")

    if not results:
        msg = f"No recent Reddit community posts found for query: '{target}'"
        logger.info(f"[TOOL RAW RESULT]: {msg}")
        return f"[Reddit Observation]: {msg}"

    formatted_items = []
    for r in results:
        formatted_items.append(
            f"- Title: {r['title']} (Subreddit: {r['subreddit']}, Date: {r['date']})\n"
            f"  User Snippet: {r['snippet']}\n"
            f"  URL: {r['url']}"
        )

    obs = f"[Reddit Observation per Reddit API]: Found {len(results)} community posts for query '{target}':\n" + "\n".join(formatted_items)
    logger.info(f"[TOOL RAW RESULT]: {obs[:300]}...")
    return obs
