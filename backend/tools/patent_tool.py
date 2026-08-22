"""
Patent search with India-first jurisdiction preference.

Source history and why this file looks the way it does
------------------------------------------------------
PatentsView is gone. Verified live (August 2026):

  * ``search.patentsview.org``          -> DNS no longer resolves
  * ``api.patentsview.org``             -> serves the USPTO Open Data Portal landing page
  * ``ped.uspto.gov`` (PEDS)            -> DNS no longer resolves
  * ``developer.uspto.gov/*-api``       -> now redirect to the ODP landing page
  * ``api.uspto.gov`` (ODP)             -> HTTP 401 without a key, and is US-only regardless
  * ``worldwide.espacenet.com`` classic -> HTTP 403
  * WIPO PATENTSCOPE                    -> connection reset, no public API
  * Lens.org / PQAI                     -> HTTP 401, key required
  * India InPASS (ipindia.gov.in)       -> JSF UI with viewstate + captcha, no API

No keyless *official* patent API survives, so this tool degrades across three
tiers instead of pretending a single source is reliable:

  Tier 1  EPO OPS (``EPO_OPS_KEY`` + ``EPO_OPS_SECRET``, free self-service key).
          Official, global, and — unlike the USPTO ODP — it indexes Indian
          publications, so it is the only tier that satisfies an India-first
          request with authoritative data.
  Tier 2  Google Patents' internal XHR endpoint. Keyless and returns Indian
          patents with assignee/inventor/filing-date metadata, but it throttles
          to HTTP 503 aggressively and stays throttled for minutes, so it is a
          best-effort tier and never retried in a loop.
  Tier 3  DuckDuckGo web search restricted to patents.google.com. Always
          available, lowest fidelity.

Every tier labels itself in the observation text. The agent must never present a
web-search fallback as a verified patent-database query.
"""

import os
import re
import time
import logging
import urllib.parse
from typing import List, Dict, Any, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

EPO_AUTH_URL = "https://ops.epo.org/3.2/auth/accesstoken"
EPO_SEARCH_URL = "https://ops.epo.org/3.2/rest-services/published-data/search/biblio"
GOOGLE_PATENTS_XHR = "https://patents.google.com/xhr/query"

# Jurisdictions surfaced first when a result set spans several countries. The
# user's brief prefers Indian coverage, so IN outranks everything; WO (PCT) is
# next because an Indian applicant's international filings appear there.
JURISDICTION_PRIORITY = {"IN": 0, "WO": 1, "EP": 2, "US": 3}

# OPS access tokens last 20 minutes. Cached module-side so a multi-competitor
# scan spends one auth round-trip instead of one per patent lookup.
_ops_token: Optional[str] = None
_ops_token_expiry: float = 0.0

_NOISE_TERMS = ("competitors:", "track", "patents", "patent", "filings", "filing")


def _clean(query: str) -> str:
    """Strips orchestration boilerplate out of an agent-supplied query string."""
    cleaned = query
    for term in _NOISE_TERMS:
        cleaned = re.sub(re.escape(term), " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,-")
    return cleaned or "multilingual language model"


def _jurisdiction_rank(country: str) -> int:
    return JURISDICTION_PRIORITY.get((country or "").upper(), 50)


def _normalize_pub(raw: str) -> str:
    """
    Normalises a Google Patents publication identifier to a bare number.

    The XHR endpoint is inconsistent: some records carry ``IN2014DN09942A`` in
    ``publication_number`` while the sibling ``id`` field is the routed form
    ``patent/IN2014DN09942A/en``. Slicing ``[:2]`` off the routed form yields the
    country code "PA", so both shapes are collapsed here before anything reads a
    jurisdiction or builds a URL from it.
    """
    value = (raw or "").strip()
    if value.startswith("patent/"):
        value = value[len("patent/"):]
    value = value.split("/")[0]
    return value.replace(" ", "")


# ---------------------------------------------------------------------------
# Tier 1: EPO OPS
# ---------------------------------------------------------------------------
def _ops_credentials() -> Tuple[str, str]:
    return (
        os.getenv("EPO_OPS_KEY", "").strip(),
        os.getenv("EPO_OPS_SECRET", "").strip(),
    )


def _ops_access_token() -> Optional[str]:
    """
    Fetches (and caches) an OPS OAuth2 client-credentials token.

    Returns None when credentials are absent or auth fails, so callers fall
    through to the keyless tiers rather than raising.
    """
    global _ops_token, _ops_token_expiry

    key, secret = _ops_credentials()
    if not key or not secret:
        return None

    if _ops_token and time.monotonic() < _ops_token_expiry:
        return _ops_token

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                EPO_AUTH_URL,
                auth=(key, secret),
                data={"grant_type": "client_credentials"},
                headers={"Accept": "application/json"},
            )
        if resp.status_code != 200:
            logger.warning(f"[EPO OPS] Auth failed: HTTP {resp.status_code} - {resp.text[:160]}")
            return None

        payload = resp.json()
        token = payload.get("access_token")
        if not token:
            logger.warning("[EPO OPS] Auth response contained no access_token.")
            return None

        # Renew a minute early to avoid racing the server-side expiry.
        lifetime = float(payload.get("expires_in", 1200) or 1200)
        _ops_token = token
        _ops_token_expiry = time.monotonic() + max(60.0, lifetime - 60.0)
        logger.info(f"[EPO OPS] Access token acquired (valid ~{int(lifetime)}s).")
        return token
    except Exception as e:
        logger.warning(f"[EPO OPS] Auth request failed: {e}")
        return None


def _ops_text(node: Any) -> str:
    """
    Unwraps an OPS JSON value.

    OPS wraps text as ``{"$": "value"}``, and any repeatable element is a bare
    object when there is one occurrence and a list when there are several. Both
    shapes appear in the same response, so every read goes through here.
    """
    if node is None:
        return ""
    if isinstance(node, str):
        return node.strip()
    if isinstance(node, dict):
        if "$" in node:
            return str(node["$"]).strip()
        if "name" in node:
            return _ops_text(node["name"])
        return ""
    if isinstance(node, list):
        for entry in node:
            text = _ops_text(entry)
            if text:
                return text
    return ""


def _as_list(node: Any) -> List[Any]:
    if node is None:
        return []
    return node if isinstance(node, list) else [node]


def _ops_names(parties: Dict[str, Any], group: str, singular: str) -> List[str]:
    """
    Collects applicant or inventor names, preferring the original-language form.

    OPS returns each party twice, once as ``epodoc`` (normalised, uppercased)
    and once as ``original``. The original reads far better in a UI, so it wins
    when present, and duplicates are dropped case-insensitively.
    """
    entries = _as_list((parties.get(group) or {}).get(singular))
    preferred: List[str] = []
    fallback: List[str] = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = _ops_text(entry.get(f"{singular}-name"))
        if not name:
            continue
        if entry.get("@data-format") == "original":
            preferred.append(name)
        else:
            fallback.append(name)

    seen = set()
    out = []
    for name in (preferred or fallback):
        marker = name.lower()
        if marker in seen:
            continue
        seen.add(marker)
        out.append(name)
    return out


def _ops_date(biblio: Dict[str, Any], ref_key: str) -> str:
    """Reads a YYYYMMDD date out of a publication/application reference as YYYY-MM-DD."""
    for doc_id in _as_list((biblio.get(ref_key) or {}).get("document-id")):
        if not isinstance(doc_id, dict):
            continue
        raw = _ops_text(doc_id.get("date"))
        if len(raw) == 8 and raw.isdigit():
            return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    return ""


def _parse_ops_document(doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Maps one OPS exchange-document onto this project's patent record shape."""
    if not isinstance(doc, dict):
        return None

    country = (doc.get("@country") or "").upper()
    number = doc.get("@doc-number") or ""
    kind = doc.get("@kind") or ""
    if not country or not number:
        return None

    publication_number = f"{country}{number}{kind}"
    biblio = doc.get("bibliographic-data") or {}
    parties = biblio.get("parties") or {}

    titles = [t for t in (_ops_text(t) for t in _as_list(biblio.get("invention-title"))) if t]
    title = titles[0] if titles else ""

    applicants = _ops_names(parties, "applicants", "applicant")
    inventors = _ops_names(parties, "inventors", "inventor")
    pub_date = _ops_date(biblio, "publication-reference")
    filing_date = _ops_date(biblio, "application-reference")

    abstract = ""
    for abs_node in _as_list(biblio.get("abstract") or doc.get("abstract")):
        if isinstance(abs_node, dict):
            abstract = " ".join(_ops_text(p) for p in _as_list(abs_node.get("p"))).strip()
            if abstract:
                break

    return {
        "publication_number": publication_number,
        "country": country,
        "title": title,
        "assignees": applicants,
        "inventors": inventors,
        "filing_date": filing_date,
        "publication_date": pub_date,
        "abstract": abstract,
        "family_id": doc.get("@family-id") or "",
        "url": f"https://worldwide.espacenet.com/patent/search?q=pn%3D{publication_number}",
    }


def _search_epo_ops(terms: str, max_results: int) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Queries EPO OPS, India-scoped first and then worldwide.

    The India-scoped pass uses the CQL clause ``pn=IN`` (publication-number
    country prefix). If that clause is rejected or empty the worldwide pass
    still runs, so an unsupported filter degrades coverage rather than the tool.
    """
    token = _ops_access_token()
    if not token:
        if not all(_ops_credentials()):
            return [], "EPO_OPS_KEY/EPO_OPS_SECRET are not configured"
        return [], "EPO OPS rejected the configured credentials"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "IntelPulse-Autonomous-Agent/1.0",
    }
    safe_terms = terms.replace('"', " ").strip()
    queries = [
        (f'ti,ab all "{safe_terms}" and pn=IN', "India-scoped"),
        (f'ti,ab all "{safe_terms}"', "worldwide"),
    ]

    collected: List[Dict[str, Any]] = []
    seen: set = set()
    note: Optional[str] = None

    for cql, label in queries:
        if len(collected) >= max_results:
            break
        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.get(
                    EPO_SEARCH_URL,
                    params={"q": cql, "Range": f"1-{max(1, min(25, max_results * 2))}"},
                    headers=headers,
                )
            logger.info(f"[EPO OPS] {label} search returned HTTP {resp.status_code}.")
            if resp.status_code != 200:
                logger.warning(f"[EPO OPS] {label} search rejected: {resp.text[:200]}")
                if resp.status_code in (403, 429):
                    note = f"EPO OPS returned HTTP {resp.status_code} (quota or fair-use limit)"
                continue

            search = (
                resp.json()
                .get("ops:world-patent-data", {})
                .get("ops:biblio-search", {})
                .get("ops:search-result", {})
            )
            for wrapper in _as_list(search.get("exchange-documents")):
                if not isinstance(wrapper, dict):
                    continue
                for doc in _as_list(wrapper.get("exchange-document")):
                    record = _parse_ops_document(doc)
                    if not record or record["publication_number"] in seen:
                        continue
                    seen.add(record["publication_number"])
                    collected.append(record)
        except Exception as e:
            logger.warning(f"[EPO OPS] {label} search failed: {e}")
            note = "the EPO OPS request failed"

    return collected, (None if collected else note)


# ---------------------------------------------------------------------------
# Tier 2: Google Patents internal XHR
# ---------------------------------------------------------------------------
def _family_coverage(patent: Dict[str, Any]) -> List[str]:
    """
    Extracts the jurisdictions where a patent family is currently active.

    This is the single highest-value field the Google endpoint exposes: it shows
    where a competitor actually holds enforceable protection, not merely where
    they filed.
    """
    aggregated = ((patent.get("family_metadata") or {}).get("aggregated") or {})
    active = []
    for entry in aggregated.get("country_status") or []:
        if not isinstance(entry, dict):
            continue
        code = (entry.get("country_code") or "").upper()
        state = ((entry.get("best_patent_stage") or {}).get("state") or "").upper()
        if code and state == "ACTIVE":
            active.append(code)
    return sorted(set(active))


def _google_patents_pass(terms: str, country: Optional[str],
                         max_results: int) -> Tuple[List[Dict[str, Any]], bool]:
    """
    One best-effort call to the Google Patents XHR endpoint. No retry loop.

    Returns (records, throttled). The throttled flag is propagated all the way to
    the observation text: "we were blocked" and "there are no such patents" are
    different facts, and reporting the first as the second is how an agent ends up
    asserting a competitor has no IP when it simply could not look.
    """
    inner = f"q={urllib.parse.quote_plus(terms)}"
    if country:
        inner += f"&country={country}"
    url = f"{GOOGLE_PATENTS_XHR}?url={urllib.parse.quote(inner, safe='')}"

    scope = country or "worldwide"
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/126 Safari/537.36"
                    ),
                    "Accept": "application/json",
                },
            )
        if resp.status_code == 503:
            # Documented behaviour of this endpoint: it throttles per-IP and stays
            # throttled for minutes. Retrying with backoff was measured to fail on
            # every attempt, so the tool moves on instead of burning the timeout.
            logger.warning(f"[Google Patents] Throttled (HTTP 503) on the {scope} pass; skipping this tier.")
            return [], True
        if resp.status_code != 200:
            logger.warning(f"[Google Patents] {scope} pass returned HTTP {resp.status_code}.")
            return [], resp.status_code in (429, 403)

        clusters = (resp.json().get("results") or {}).get("cluster") or []
        records: List[Dict[str, Any]] = []
        for cluster in clusters:
            for entry in (cluster or {}).get("result") or []:
                patent = (entry or {}).get("patent") or {}
                pub = _normalize_pub(patent.get("publication_number") or (entry or {}).get("id") or "")
                if not pub:
                    continue

                title = re.sub(r"<[^>]+>", "", patent.get("title") or "").strip()
                snippet = re.sub(r"<[^>]+>", "", patent.get("snippet") or "").strip()
                assignee = (patent.get("assignee") or "").strip()

                records.append({
                    "publication_number": pub,
                    "country": pub[:2].upper(),
                    # Indian publications frequently carry a placeholder title on this
                    # endpoint (e.g. " Patent IN2014DN09942A"), so the assignee and
                    # snippet are what actually convey meaning downstream.
                    "title": title or f"Patent {pub}",
                    "assignees": [assignee] if assignee else [],
                    "inventors": [i for i in [(patent.get("inventor") or "").strip()] if i],
                    "filing_date": patent.get("filing_date") or "",
                    "publication_date": patent.get("publication_date") or "",
                    "abstract": snippet,
                    "family_id": "",
                    "active_jurisdictions": _family_coverage(patent),
                    "url": f"https://patents.google.com/patent/{pub}/en",
                })
                if len(records) >= max_results * 2:
                    break
        logger.info(f"[Google Patents] {scope} pass parsed {len(records)} records.")
        return records, False
    except Exception as e:
        logger.warning(f"[Google Patents] {scope} pass failed: {e}")
        return [], False


def _search_google_patents(terms: str, max_results: int) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """India-scoped pass first, then worldwide if India returned too little."""
    collected, throttled = _google_patents_pass(terms, "IN", max_results)
    seen = {r["publication_number"] for r in collected}

    if len(collected) < max_results:
        more, more_throttled = _google_patents_pass(terms, None, max_results)
        throttled = throttled or more_throttled
        for record in more:
            if record["publication_number"] in seen:
                continue
            seen.add(record["publication_number"])
            collected.append(record)

    note = None
    if not collected and throttled:
        note = "the keyless Google Patents endpoint rate-limited this request (HTTP 503)"
    return collected, note


# ---------------------------------------------------------------------------
# Tier 3: web search
# ---------------------------------------------------------------------------
def _search_web_fallback(terms: str, max_results: int) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Last-resort web search restricted to Google Patents result pages.

    Several query shapes are tried in order because the upstream search backend
    silently returns zero hits for an over-constrained query: a quoted exact
    phrase plus a ``site:`` operator was measured returning 0 for topics that do
    have matching patents. Loosening the query is the difference between a
    degraded answer and no answer.
    """
    records: List[Dict[str, Any]] = []
    seen: set = set()
    note: Optional[str] = None

    formulations = [
        f'{terms} patent site:patents.google.com',
        f'site:patents.google.com {terms}',
        f'"{terms}" patent site:patents.google.com',
        f'{terms} patent google patents',
    ]

    # The package was renamed duckduckgo-search -> ddgs. Prefer the new name and
    # keep the old import as a fallback so an environment that has not reinstalled
    # yet still works; importing the retired name emits a RuntimeWarning on every
    # call, which is why the new name is tried first rather than second.
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS
        except Exception as e:
            logger.error(f"[Patents web fallback] neither ddgs nor duckduckgo-search is importable: {e}")
            return [], "the web-search fallback library is not installed"

    for formulation in formulations:
        if len(records) >= max_results:
            break
        try:
            logger.info(f"[Patents web fallback] Trying: {formulation}")
            # Positional, not keywords=: ddgs renamed the first parameter to
            # ``query``, while the retired duckduckgo-search called it
            # ``keywords``. Passing it positionally is the only form both accept.
            results = list(DDGS().text(formulation, max_results=max_results * 3))
        except Exception as e:
            logger.warning(f"[Patents web fallback] '{formulation}' failed: {e}")
            note = "the web-search fallback was rate-limited or unreachable"
            continue

        logger.info(f"[Patents web fallback] {len(results)} raw hits.")
        for item in results:
            url = item.get("href") or item.get("url") or ""
            if "patents.google.com/patent/" not in url:
                continue

            title = (item.get("title") or "").replace(" - Google Patents", "").strip()
            if any(bad in title.lower() for bad in ("merriam-webster", "wikipedia", "dictionary", "forum", "blog")):
                continue

            match = re.search(r"/patent/([A-Z]{2}[^/]+)", url)
            pub = match.group(1) if match else ""
            if pub and pub in seen:
                continue
            if pub:
                seen.add(pub)

            records.append({
                "publication_number": pub or "Patent filing",
                "country": pub[:2].upper() if pub else "",
                "title": title or "Patent filing",
                "assignees": [],
                "inventors": [],
                "filing_date": "",
                "publication_date": "",
                "abstract": (item.get("body") or item.get("snippet") or "").strip(),
                "family_id": "",
                "url": url,
            })
            if len(records) >= max_results * 2:
                break

    return records, (None if records else note)


# ---------------------------------------------------------------------------
# Presentation
# ---------------------------------------------------------------------------
def _build_snippet(record: Dict[str, Any]) -> str:
    """
    Composes the analyst-facing snippet.

    Assignee, inventor and filing date lead because "who owns this and since
    when" is the competitive question; the abstract follows as supporting text.
    A raw abstract alone — which is all the previous PatentsView version showed
    — cannot answer it.
    """
    parts: List[str] = []
    if record.get("assignees"):
        parts.append(f"Assignee: {', '.join(record['assignees'][:2])}")
    if record.get("inventors"):
        parts.append(f"Inventor: {record['inventors'][0]}")
    if record.get("filing_date"):
        parts.append(f"Filed: {record['filing_date']}")
    if record.get("active_jurisdictions"):
        parts.append(f"Active in: {', '.join(record['active_jurisdictions'][:6])}")
    if record.get("family_id"):
        parts.append(f"Family: {record['family_id']}")

    header = " | ".join(parts)
    abstract = (record.get("abstract") or "").strip()

    if header and abstract:
        return f"{header}. {abstract}"[:400]
    return (header or abstract or "No abstract or assignee metadata available.")[:400]


def _source_name(record: Dict[str, Any], tier_label: str) -> str:
    """ASCII-only label; this string reaches a possibly cp1252 log stream."""
    country = record.get("country") or ""
    pub = record.get("publication_number") or ""
    bits = [tier_label]
    if country:
        bits.append(country)
    if pub and pub != "Patent filing":
        bits.append(pub)
    return " | ".join(bits)


def search_patents(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Searches patent filings for a topic or company, preferring Indian jurisdictions.

    Tries EPO OPS (official, needs a free key), then the keyless Google Patents
    XHR endpoint, then a labelled Google Patents web search. The observation text
    always names the tier that produced the data so a fallback is never presented
    as a verified database query.

    Returns {"text": <observation for the LLM>, "items": [...], "source_type": "patents"}.
    """
    terms = _clean(query)
    logger.info(f"--- [TOOL CALL] search_patents(query='{terms}') ---")

    tiers = [
        ("EPO OPS", "EPO OPS (official patent database, India-first)", _search_epo_ops),
        ("Google Patents", "Google Patents data API (keyless, India-first)", _search_google_patents),
        ("web search", "Google Patents WEB SEARCH fallback (NOT a verified patent database query)", _search_web_fallback),
    ]

    records: List[Dict[str, Any]] = []
    tier_label = ""
    source_label = ""
    attempted: List[str] = []
    notes: List[str] = []

    for short_name, label, fn in tiers:
        attempted.append(short_name)
        records, note = fn(terms, max_results)
        if note:
            notes.append(note)
        if records:
            tier_label, source_label = short_name, label
            logger.info(f"[Patents] Tier '{short_name}' returned {len(records)} records.")
            break
        logger.info(f"[Patents] Tier '{short_name}' returned nothing; trying the next tier.")

    if not records:
        # Distinguish "blocked" from "nothing exists". Every keyless patent
        # endpoint now throttles or is retired, so a bare "no patents found"
        # would read as a factual claim about the competitor's IP position
        # when it is really a claim about our access.
        if notes:
            reason = (
                "Every tier degraded rather than returning data: "
                + "; ".join(notes)
                + ". This means patent coverage is UNAVAILABLE for this query, not that "
                "no patents exist. Do not conclude anything about the subject's IP position."
            )
        else:
            reason = "All tiers responded but matched no filings, so no patents were found for these terms."

        msg = f"No patent filings retrieved for '{terms}'. Tiers attempted: {', '.join(attempted)}. {reason}"
        logger.info(f"[TOOL RAW RESULT]: {msg}")
        return {"text": f"[Patent Observation]: {msg}", "items": [], "source_type": "patents"}

    # India first, then PCT/EP/US, then everything else; ties broken by recency.
    records.sort(key=lambda r: (
        _jurisdiction_rank(r.get("country", "")),
        -int((r.get("publication_date") or "0").replace("-", "")[:8] or 0),
    ))
    records = records[:max_results]

    indian = sum(1 for r in records if r.get("country") == "IN")
    formatted = []
    for r in records:
        formatted.append(
            f"- {r['title']} ({r['publication_number']}, {r.get('country') or 'unknown jurisdiction'}, "
            f"published {r.get('publication_date') or 'date unavailable'})\n"
            f"  {_build_snippet(r)}\n"
            f"  URL: {r['url']}"
        )

    obs = (
        f"[{source_label}]: Found {len(records)} patent records for '{terms}' "
        f"({indian} Indian jurisdiction):\n" + "\n".join(formatted)
    )
    logger.info(f"[TOOL RAW RESULT]: {obs[:300]}...")

    items = [
        {
            "title": r["title"],
            "snippet": _build_snippet(r),
            "source_name": _source_name(r, tier_label),
            "date": r.get("publication_date") or r.get("filing_date") or "Recent",
            "url": r["url"],
        }
        for r in records
    ]
    return {"text": obs, "items": items, "source_type": "patents"}
