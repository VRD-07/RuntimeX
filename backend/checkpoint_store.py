"""Single persistence layer for the agent graph.

LangGraph's ``SqliteSaver`` is the *only* store used by the graph: it holds both
the per-run checkpoints (durability, replay, resume) and the cross-run
long-term memory. There is deliberately no second table and no second database
file — the brief for this build called for one persistence layer, and having
two is how the old code ended up with a gap report that disagreed with the
checkpointed state.

How cross-run memory works without a second store
-------------------------------------------------
Every run gets its own thread id, namespaced by the ``(topic, competitor)`` pair
it is about::

    scan::<topic-slug>::<competitor-slug>::<run-token>

To recall, we list the checkpointer's own threads, keep the ones whose id starts
with the same ``scan::<topic>::<competitor>::`` prefix, and load the newest
*other* thread's final state. That is a real read of a real prior checkpoint —
not a summary we wrote to the side — so anything the previous run computed
(gap report, item counts, summary) is available verbatim.

A fresh thread per run is what keeps run-scoped lists (observations, trace) from
bleeding between runs, which is what would happen if repeat scans of the same
competitor reused one thread.
"""

import logging
import os
import re
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from langgraph.checkpoint.sqlite import SqliteSaver

logger = logging.getLogger(__name__)

DEFAULT_DB_FILENAME = "intelpulse_graph.sqlite"
THREAD_PREFIX = "scan"

_conn: Optional[sqlite3.Connection] = None
_saver: Optional[SqliteSaver] = None
_lock = threading.Lock()


def _slug(value: str) -> str:
    """Collapses free text to a stable, filesystem-safe thread-id fragment."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return (cleaned or "unspecified")[:48]


def db_path() -> str:
    """
    Resolves the checkpoint database path.

    MEMORY_DB_PATH is reused rather than introducing a new variable: it already
    points at the mounted persistent disk on Render, which is exactly where the
    checkpoints need to live. If it names a directory, the default filename is
    appended; if it names a ``.db``/``.sqlite`` file, that file is used.
    """
    configured = (os.getenv("MEMORY_DB_PATH", "") or "").strip()
    if not configured:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_FILENAME)
    if os.path.isdir(configured) or configured.endswith(("/", "\\")):
        return os.path.join(configured, DEFAULT_DB_FILENAME)
    return configured


def get_saver() -> SqliteSaver:
    """
    Returns the process-wide SqliteSaver, creating it on first use.

    ``check_same_thread=False`` is required because FastAPI runs sync endpoints
    in a threadpool, so the connection is touched from more than one thread.
    SqliteSaver serialises its own writes; WAL mode keeps concurrent reads from
    blocking behind them.
    """
    global _conn, _saver
    with _lock:
        if _saver is not None:
            return _saver

        path = db_path()
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)

        _conn = sqlite3.connect(path, check_same_thread=False)
        try:
            _conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.Error as e:  # pragma: no cover - depends on filesystem
            logger.warning(f"[Checkpoint] Could not enable WAL on {path}: {e}")
        _saver = SqliteSaver(_conn)
        _saver.setup()
        logger.info(f"[Checkpoint] SqliteSaver ready at {path}")
        return _saver


def memory_key(topic: str, competitor: str) -> str:
    """The thread-id prefix shared by every run about this (topic, competitor)."""
    return f"{THREAD_PREFIX}::{_slug(topic)}::{_slug(competitor)}"


def new_thread_id(topic: str, competitor: str) -> str:
    """A unique thread id for one run, still grouped under its memory key."""
    return f"{memory_key(topic, competitor)}::{int(time.time() * 1000)}"


def _list_threads() -> List[Tuple[str, Any]]:
    """
    All (thread_id, checkpoint_tuple) pairs known to the checkpointer.

    ``SqliteSaver.list(None)`` walks every thread. It is called with no filter
    because we need to group by our own id prefix, which the checkpointer has no
    concept of.
    """
    saver = get_saver()
    found: List[Tuple[str, Any]] = []
    try:
        for item in saver.list(None):
            thread_id = (item.config or {}).get("configurable", {}).get("thread_id")
            if thread_id:
                found.append((thread_id, item))
    except Exception as e:
        logger.warning(f"[Checkpoint] Could not list threads: {e}")
    return found


def recall_prior_run(topic: str, competitor: str, exclude_thread: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Loads the most recent *completed prior* run for this (topic, competitor).

    Returns a plain dict of the fields the graph reasons over, or None when this
    is the first run for the pair. ``exclude_thread`` skips the run in progress.

    Falls back to any thread under the same competitor when the topic differs,
    so a competitor scanned before under another topic still contributes memory —
    flagged with ``topic_match: False`` so the trace can say so rather than
    implying an exact prior match.
    """
    exact_prefix = memory_key(topic, competitor) + "::"
    comp_fragment = f"::{_slug(competitor)}::"

    exact: List[Tuple[str, Any]] = []
    loose: List[Tuple[str, Any]] = []
    for thread_id, item in _list_threads():
        if exclude_thread and thread_id == exclude_thread:
            continue
        if thread_id.startswith(exact_prefix):
            exact.append((thread_id, item))
        elif comp_fragment in thread_id:
            loose.append((thread_id, item))

    pool, topic_match = (exact, True) if exact else (loose, False)
    if not pool:
        return None

    # Thread ids end in a millisecond timestamp, so lexical order is chronological.
    pool.sort(key=lambda pair: pair[0], reverse=True)
    thread_id, item = pool[0]

    values = getattr(item, "checkpoint", {}).get("channel_values", {}) or {}
    sections = values.get("sections") or []
    item_count = sum(len(s.get("items") or []) for s in sections if isinstance(s, dict))

    return {
        "thread_id": thread_id,
        "topic": values.get("topic") or "",
        "competitor": competitor,
        "topic_match": topic_match,
        "gap_report": values.get("gap_report") or [],
        "executive_summary": values.get("executive_summary") or "",
        "item_count": item_count,
        "conflict_count": len(values.get("conflict_log") or []),
        "tool_calls_used": values.get("tool_calls_used") or 0,
        "timestamp": getattr(item, "checkpoint", {}).get("ts") or "",
        "seeded": bool(values.get("seeded_baseline")),
        "provenance": "seeded_baseline" if values.get("seeded_baseline") else "prior_run_checkpoint",
    }


def compute_delta(prior: Optional[Dict[str, Any]], competitor: str,
                  gap_report: List[Dict[str, Any]], item_count: int) -> str:
    """
    Describes what changed since the recalled run, in plain language.

    Deliberately computed from two real numbers (prior vs current item count) and
    two real gap lists, so the delta cannot drift from what the runs actually
    found the way a model-written delta would.
    """
    now_gapped = any(g.get("entity") == competitor for g in gap_report)

    if not prior:
        state = "still thin" if now_gapped else "adequately covered"
        return (
            f"Baseline established: first recorded run for '{competitor}'. "
            f"{item_count} grounded item(s) retrieved; coverage is {state}."
        )

    origin = "seeded baseline" if prior.get("seeded") else f"prior run {prior.get('thread_id', '')[-13:]}"
    was_gapped = any(g.get("entity") == competitor for g in (prior.get("gap_report") or []))
    prior_count = prior.get("item_count") or 0
    change = item_count - prior_count

    if change > 0:
        volume = f"coverage grew by {change} item(s) ({prior_count} -> {item_count})"
    elif change < 0:
        volume = f"coverage fell by {abs(change)} item(s) ({prior_count} -> {item_count})"
    else:
        volume = f"coverage unchanged at {item_count} item(s)"

    if was_gapped and not now_gapped:
        movement = "the gap flagged previously is now closed"
    elif not was_gapped and now_gapped:
        movement = "a new coverage gap opened that was not present before"
    elif was_gapped and now_gapped:
        movement = "the same coverage gap persists across both runs"
    else:
        movement = "no coverage gap in either run"

    scope = "" if prior.get("topic_match") else f" (compared against a different topic: '{prior.get('topic')}')"
    return f"Versus {origin}{scope}: {volume}; {movement}."


# ---------------------------------------------------------------------------
# Baseline seeding
# ---------------------------------------------------------------------------
SEED_TOPIC = "Regional language capabilities for AI"
SEED_COMPETITORS = ["Sarvam", "OpenAI", "Google"]


def seed_baseline_if_empty() -> int:
    """
    Writes one labelled baseline checkpoint per demo competitor if the store is empty.

    Render's default disk is ephemeral, so a fresh deploy would otherwise have
    nothing to recall and the memory-based reasoning path would be invisible in a
    demo. Each seeded checkpoint carries ``seeded_baseline: True``, and every
    consumer surfaces that as "seeded baseline" rather than "prior scan", so a
    seeded value can never be mistaken for something the agent actually observed.

    Returns the number of baselines written (0 if the store already had data).
    """
    saver = get_saver()
    if _list_threads():
        return 0

    written = 0
    for competitor in SEED_COMPETITORS:
        thread_id = f"{memory_key(SEED_TOPIC, competitor)}::0"
        config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
        checkpoint = {
            "v": 1,
            "id": f"seed-{_slug(competitor)}",
            "ts": "1970-01-01T00:00:00+00:00",
            "channel_values": {
                "topic": SEED_TOPIC,
                "competitors": ", ".join(SEED_COMPETITORS),
                "seeded_baseline": True,
                "sections": [],
                "gap_report": [{
                    "entity": competitor,
                    "gap": "Seeded baseline placeholder - no observations were retrieved for this entry.",
                    "item_count": 0,
                    "confidence": 0.0,
                    "provenance": "seeded_baseline",
                }],
                "executive_summary": (
                    f"Seeded baseline for {competitor}. This is demo scaffolding written at startup "
                    f"so cross-run memory has something to compare against on a fresh deploy. It is "
                    f"not a real observation and contains no retrieved evidence."
                ),
                "conflict_log": [],
                "tool_calls_used": 0,
            },
            "channel_versions": {},
            "versions_seen": {},
        }
        try:
            saver.put(config, checkpoint, {"source": "update", "step": -1, "parents": {}}, {})
            written += 1
        except Exception as e:
            logger.warning(f"[Checkpoint] Baseline seed for '{competitor}' failed: {e}")

    if written:
        logger.info(f"[Checkpoint] Seeded {written} labelled baseline checkpoint(s) into an empty store.")
    return written


def store_stats() -> Dict[str, Any]:
    """Counts for /api/health so the store's state is observable without a shell."""
    threads = _list_threads()
    seeded = sum(
        1 for _, item in threads
        if (getattr(item, "checkpoint", {}).get("channel_values", {}) or {}).get("seeded_baseline")
    )
    return {
        "path": db_path(),
        "threads": len({t for t, _ in threads}),
        "checkpoints": len(threads),
        "seeded_baselines": seeded,
    }
