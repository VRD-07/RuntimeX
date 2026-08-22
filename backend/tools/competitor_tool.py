import os
import re
import time
import httpx
import logging
import html
import urllib.parse
import xml.etree.ElementTree as ET
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def search_news(query: str, max_results: int = 5) -> str:
    """
    Finds recent news articles using real News APIs (NewsAPI.org / GNews / Official Google News API).
    Zero DuckDuckGo scrapers used. Includes retry-with-backoff and logs the exact request URL.
    """
    clean_query = query.replace("Competitors:", "").replace("Track", "").replace("news", "").strip()
    if not clean_query:
        clean_query = "Sarvam AI"

    encoded_query = urllib.parse.quote(clean_query)
    news_api_key = os.getenv("NEWS_API_KEY", "").strip()
    gnews_api_key = os.getenv("GNEWS_API_KEY", "").strip()

    logger.info(f"--- [TOOL CALL] search_news(query='{clean_query}') ---")
    news_items = []
    source_name_label = "News API"

    # Select endpoint: NewsAPI.org -> GNews -> Official Google News RSS API
    if news_api_key:
        url = f"https://newsapi.org/v2/everything?q={encoded_query}&language=en&pageSize={max_results}&apiKey={news_api_key}"
        source_name_label = "NewsAPI.org"
    elif gnews_api_key:
        url = f"https://gnews.io/api/v4/search?q={encoded_query}&lang=en&max={max_results}&apikey={gnews_api_key}"
        source_name_label = "GNews API"
    else:
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
        source_name_label = "Google News API"

    logger.info(f"[News API Call]: Executing request URL: '{url}'")

    headers = {"User-Agent": "IntelPulse-Autonomous-Agent/1.0 (Windows NT 10.0; Win64; x64)"}

    # Execute request with retry-with-backoff (1 retry after 1.5 seconds)
    response = None
    for attempt in range(2):
        try:
            with httpx.Client(timeout=12.0) as client:
                res = client.get(url, headers=headers, follow_redirects=True)
                logger.info(f"[News API Raw Status]: HTTP {res.status_code} (Attempt {attempt+1})")
                if res.status_code == 200:
                    response = res
                    break
                elif res.status_code in [429, 500, 502, 503, 504] and attempt == 0:
                    logger.warning(f"[News API Retry]: Received HTTP {res.status_code}. Retrying in 1.5s...")
                    time.sleep(1.5)
                else:
                    logger.error(f"[News API Error]: HTTP {res.status_code} - Body: {res.text[:200]}")
                    break
        except Exception as e:
            if attempt == 0:
                logger.warning(f"[News API Exception]: {e}. Retrying in 1.5s...")
                time.sleep(1.5)
            else:
                logger.error(f"[News API Exception Failed]: {e}")

    # Process response
    if response and response.status_code == 200:
        content_type = response.headers.get("content-type", "").lower()

        # Case A: JSON Response (NewsAPI.org / GNews)
        if "json" in content_type:
            try:
                data = response.json()
                articles = data.get("articles", [])
                for a in articles:
                    title = a.get("title", "").strip()
                    desc = (a.get("description") or a.get("content") or "No description provided").strip()
                    url_link = a.get("url") or "#"
                    source_title = a.get("source", {}).get("name") if isinstance(a.get("source"), dict) else "News"
                    pub_date = a.get("publishedAt", "Recent")[:10]

                    if title:
                        news_items.append({
                            "title": title,
                            "snippet": desc[:250],
                            "source_name": source_title,
                            "date": pub_date,
                            "url": url_link
                        })
                        if len(news_items) >= max_results:
                            break
            except Exception as json_err:
                logger.error(f"Error parsing JSON news response: {json_err}")

        # Case B: XML Response (Google News API RSS)
        else:
            try:
                root = ET.fromstring(response.text)
                items = root.findall(".//item")
                for item in items:
                    raw_title = item.find("title").text if item.find("title") is not None else ""
                    link = item.find("link").text if item.find("link") is not None else "#"
                    pub_date = item.find("pubDate").text if item.find("pubDate") is not None else "Recent"
                    source_elem = item.find("source")
                    source_title = source_elem.text if source_elem is not None else "Google News"
                    desc_elem = item.find("description")
                    desc_text = html.unescape(desc_elem.text) if desc_elem is not None else raw_title

                    # Clean title and HTML description
                    clean_title = html.unescape(raw_title).split(" - ")[0].strip()
                    clean_desc = re.sub(r'<[^>]+>', ' ', desc_text)
                    clean_desc = ' '.join(clean_desc.split())[:250]

                    if clean_title:
                        news_items.append({
                            "title": clean_title,
                            "snippet": clean_desc,
                            "source_name": source_title,
                            "date": pub_date[:16],
                            "url": link
                        })
                        if len(news_items) >= max_results:
                            break
            except Exception as xml_err:
                logger.error(f"Error parsing XML news response: {xml_err}")

    if not news_items:
        msg = f"No recent news articles found for query: '{clean_query}'"
        logger.info(f"[TOOL RAW RESULT]: {msg}")
        return f"[{source_name_label} Observation]: {msg}"

    formatted_items = []
    for n in news_items:
        formatted_items.append(
            f"- Title: {n['title']} (Date: {n['date']}, Source: {n['source_name']})\n"
            f"  Snippet: {n['snippet']}\n"
            f"  URL: {n['url']}"
        )

    obs = f"[{source_name_label} Observation per {source_name_label}]: Found {len(news_items)} articles for query '{clean_query}':\n" + "\n".join(formatted_items)
    logger.info(f"[TOOL RAW RESULT]: {obs[:300]}...")
    return obs
