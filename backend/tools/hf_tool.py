"""
Hugging Face model-traction search.

Why this source exists in a competitive-intelligence tool
--------------------------------------------------------
News tells you what a competitor *announced*; the Hugging Face Hub tells you
whether anyone actually uses it. Download counts, likes and release cadence are
the closest thing to a public adoption metric for an AI lab, and for Indic-
language model vendors in particular the Hub is where the artefacts land.

Keyless and unauthenticated. ``HF_TOKEN`` is honoured if present, which raises
the rate limit and exposes gated repositories, but is not required.
"""

import os
import logging
import urllib.parse
from typing import List, Dict, Any

import httpx

logger = logging.getLogger(__name__)

HF_MODELS_URL = "https://huggingface.co/api/models"

_NOISE_TERMS = (
    "competitors:", "track", "open source", "opensource",
    "models", "model", "huggingface", "hugging face",
)


def _clean(query: str) -> str:
    cleaned = query.lower()
    for term in _NOISE_TERMS:
        cleaned = cleaned.replace(term, " ")
    cleaned = " ".join(cleaned.split()).strip(" ,-")
    return cleaned or "multilingual language model"


def _humanize(count: int) -> str:
    """Compact download/like counts. ASCII only — this reaches the log stream."""
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}k"
    return str(count)


def search_huggingface_models(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Finds published models on the Hugging Face Hub and reports their traction.

    Sorted by downloads so the result set reflects real adoption rather than
    recency. Returns {"text", "items", "source_type": "models"}.
    """
    terms = _clean(query)
    logger.info(f"--- [TOOL CALL] search_huggingface_models(query='{terms}') ---")

    params = urllib.parse.urlencode({
        "search": terms,
        "limit": max(1, min(20, max_results * 3)),
        "full": "true",
        "sort": "downloads",
        "direction": -1,
    })
    url = f"{HF_MODELS_URL}?{params}"

    headers = {
        "User-Agent": "IntelPulse-Autonomous-Agent/1.0",
        "Accept": "application/json",
    }
    token = os.getenv("HF_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    records: List[Dict[str, Any]] = []
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(url, headers=headers)
        logger.info(f"[Hugging Face] HTTP {resp.status_code} for query '{terms}'.")

        if resp.status_code == 200:
            payload = resp.json()
            entries = payload if isinstance(payload, list) else []
            logger.info(f"[Hugging Face] {len(entries)} raw models returned.")

            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                model_id = entry.get("modelId") or entry.get("id") or ""
                if not model_id:
                    continue

                tags = [t for t in (entry.get("tags") or []) if isinstance(t, str)]
                records.append({
                    "id": model_id,
                    "author": entry.get("author") or (model_id.split("/")[0] if "/" in model_id else ""),
                    "downloads": int(entry.get("downloads") or 0),
                    "likes": int(entry.get("likes") or 0),
                    "task": entry.get("pipeline_tag") or "",
                    "library": entry.get("library_name") or "",
                    "gated": bool(entry.get("gated")),
                    # Non-plumbing tags only: 'license:*'/'region:*'/'arxiv:*' are
                    # metadata bookkeeping and crowd out the informative ones.
                    "tags": [t for t in tags if ":" not in t][:6],
                    "updated": (entry.get("lastModified") or "")[:10],
                    "created": (entry.get("createdAt") or "")[:10],
                    "url": f"https://huggingface.co/{model_id}",
                })
                if len(records) >= max_results:
                    break
        else:
            logger.warning(f"[Hugging Face] Returned HTTP {resp.status_code}: {resp.text[:180]}")
    except Exception as e:
        logger.error(f"[Hugging Face] Query failed for '{terms}': {e}")

    if not records:
        msg = f"No published Hugging Face models found for query: '{terms}'"
        logger.info(f"[TOOL RAW RESULT]: {msg}")
        return {"text": f"[Model Hub Observation]: {msg}", "items": [], "source_type": "models"}

    total_downloads = sum(r["downloads"] for r in records)
    formatted = []
    for r in records:
        formatted.append(
            f"- {r['id']} by {r['author'] or 'unknown'}: {r['downloads']:,} downloads, {r['likes']:,} likes\n"
            f"  Task: {r['task'] or 'unspecified'} | Library: {r['library'] or 'unspecified'}"
            f" | Last updated: {r['updated'] or 'unknown'}\n"
            f"  URL: {r['url']}"
        )

    obs = (
        f"[Hugging Face Hub Observation]: Found {len(records)} published models for '{terms}' "
        f"({total_downloads:,} combined downloads):\n" + "\n".join(formatted)
    )
    logger.info(f"[TOOL RAW RESULT]: {obs[:300]}...")

    items = []
    for r in records:
        detail = [f"{r['downloads']:,} downloads", f"{r['likes']:,} likes"]
        if r["task"]:
            detail.append(f"task: {r['task']}")
        if r["library"]:
            detail.append(f"library: {r['library']}")
        if r["gated"]:
            detail.append("gated access")
        if r["tags"]:
            detail.append("tags: " + ", ".join(r["tags"]))
        if r["created"]:
            detail.append(f"first published {r['created']}")

        items.append({
            "title": r["id"],
            "snippet": ". ".join(detail)[:400],
            "source_name": f"Hugging Face | {_humanize(r['downloads'])} downloads | {_humanize(r['likes'])} likes",
            "date": r["updated"] or "Recent",
            "url": r["url"],
        })

    return {"text": obs, "items": items, "source_type": "models"}
