"""
Hacker News discussion search (via the public Algolia index).

Why this source exists in a competitive-intelligence tool
--------------------------------------------------------
Reddit RSS captures end-user sentiment; Hacker News captures the technical and
investor-adjacent conversation, and it carries two signals Reddit's RSS feed does
not expose at all: an upvote score and a comment count. Those quantify *how much*
attention a launch got rather than merely that it was mentioned, which is the
difference between "a post exists" and "this landed".

Keyless, unauthenticated, no rate-limit headers observed.
"""

import logging
import urllib.parse
from typing import List, Dict, Any

import httpx

logger = logging.getLogger(__name__)

HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"

_NOISE_TERMS = (
    "competitors:", "track", "hacker news", "hackernews",
    "user feedback", "sentiment", "discussion", "discussions",
)


def _clean(query: str) -> str:
    cleaned = query.lower()
    for term in _NOISE_TERMS:
        cleaned = cleaned.replace(term, " ")
    cleaned = " ".join(cleaned.split()).strip(" ,-")
    return cleaned or "multilingual language model"


def search_hackernews(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Finds Hacker News stories about a company or technology, with engagement metrics.

    Returns {"text", "items", "source_type": "hackernews"}. Every item URL points at
    the HN discussion thread, not the linked article, so the citation resolves to
    the conversation the score and comment count actually describe.
    """
    terms = _clean(query)
    logger.info(f"--- [TOOL CALL] search_hackernews(query='{terms}') ---")

    params = urllib.parse.urlencode({
        "query": terms,
        "tags": "story",
        "hitsPerPage": max(1, min(20, max_results * 3)),
    })
    url = f"{HN_SEARCH_URL}?{params}"

    records: List[Dict[str, Any]] = []
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(
                url,
                headers={
                    "User-Agent": "IntelPulse-Autonomous-Agent/1.0",
                    "Accept": "application/json",
                },
            )
        logger.info(f"[Hacker News] HTTP {resp.status_code} for query '{terms}'.")

        if resp.status_code == 200:
            hits = resp.json().get("hits") or []
            logger.info(f"[Hacker News] {len(hits)} raw hits returned.")

            for hit in hits:
                if not isinstance(hit, dict):
                    continue
                title = (hit.get("title") or hit.get("story_title") or "").strip()
                object_id = hit.get("objectID") or hit.get("story_id")
                if not title or not object_id:
                    continue

                records.append({
                    "title": title,
                    "author": hit.get("author") or "unknown",
                    "points": int(hit.get("points") or 0),
                    "comments": int(hit.get("num_comments") or 0),
                    "date": (hit.get("created_at") or "")[:10],
                    "article_url": hit.get("url") or "",
                    "url": f"https://news.ycombinator.com/item?id={object_id}",
                })
                if len(records) >= max_results:
                    break
        else:
            logger.warning(f"[Hacker News] Returned HTTP {resp.status_code}: {resp.text[:180]}")
    except Exception as e:
        logger.error(f"[Hacker News] Query failed for '{terms}': {e}")

    if not records:
        msg = f"No Hacker News discussions found for query: '{terms}'"
        logger.info(f"[TOOL RAW RESULT]: {msg}")
        return {"text": f"[Hacker News Observation]: {msg}", "items": [], "source_type": "hackernews"}

    total_points = sum(r["points"] for r in records)
    total_comments = sum(r["comments"] for r in records)

    formatted = [
        f"- {r['title']} ({r['points']} points, {r['comments']} comments, "
        f"posted by {r['author']} on {r['date'] or 'unknown date'})\n"
        f"  Discussion: {r['url']}"
        + (f" | Linked article: {r['article_url']}" if r["article_url"] else "")
        for r in records
    ]

    obs = (
        f"[Hacker News Observation]: Found {len(records)} discussions for '{terms}' "
        f"({total_points} combined points, {total_comments} comments):\n" + "\n".join(formatted)
    )
    logger.info(f"[TOOL RAW RESULT]: {obs[:300]}...")

    items = []
    for r in records:
        detail = [
            f"{r['points']} points",
            f"{r['comments']} comments",
            f"submitted by {r['author']}",
        ]
        if r["article_url"]:
            detail.append(f"links to {r['article_url']}")
        items.append({
            "title": r["title"],
            "snippet": ". ".join(detail)[:400],
            "source_name": f"Hacker News | {r['points']} points | {r['comments']} comments",
            "date": r["date"] or "Recent",
            "url": r["url"],
        })

    return {"text": obs, "items": items, "source_type": "hackernews"}
