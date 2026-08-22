import sqlite3
import json
import logging
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("MEMORY_DB_PATH", "").strip() or os.path.join(os.path.dirname(__file__), "intelpulse_memory.db")

def get_db_connection():
    parent = os.path.dirname(os.path.abspath(DB_PATH))
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_memory_db():
    """Initializes SQLite database and auto-seeds baseline prior-scan memory if empty."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scan_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            competitor TEXT NOT NULL,
            timestamp DATETIME NOT NULL,
            gap_report TEXT NOT NULL,
            executive_summary TEXT NOT NULL
        )
    """)
    conn.commit()

    # Check if empty -> Auto-seed fallback baseline rows
    cursor.execute("SELECT COUNT(*) as count FROM scan_memory")
    count = cursor.fetchone()["count"]

    if count == 0:
        seed_time = (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
        topic = "Regional language capabilities for AI"

        seed_data = [
            (
                topic,
                "Sarvam",
                seed_time,
                json.dumps([{"entity": "Sarvam", "gap": "Thin patent coverage (0 verified USPTO filings found in prior scan)"}]),
                "Prior scan flagged Sarvam as having strong regional news momentum but zero documented USPTO patent filings."
            ),
            (
                topic,
                "OpenAI",
                seed_time,
                json.dumps([{"entity": "OpenAI", "gap": "No recent open-source Indic model repositories on GitHub"}]),
                "Prior scan noted high news mentions for OpenAI India initiatives but thin open-source repository contributions."
            ),
            (
                topic,
                "Google",
                seed_time,
                json.dumps([{"entity": "Google", "gap": "Thin Reddit community sentiment on Indic LLM benchmark evaluations"}]),
                "Prior scan evaluated Gemini multilingual capabilities with strong ArXiv research citations but limited user sentiment feedback."
            )
        ]

        cursor.executemany("""
            INSERT INTO scan_memory (topic, competitor, timestamp, gap_report, executive_summary)
            VALUES (?, ?, ?, ?, ?)
        """, seed_data)
        conn.commit()
        logger.info(f"[Memory DB] Auto-seeded baseline prior scan memory (3 records, timestamped {seed_time}).")

    conn.close()

def get_prior_scan_memory(topic: str, competitor: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves the most recent prior scan record for a competitor.

    Prefers a record for the same (competitor, topic) pair. If none exists, falls back to the
    most recent record for that competitor under any topic and flags it with topic_match=False
    so callers can describe the recall honestly.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    clean_comp = competitor.strip()
    clean_topic = topic.strip()

    # 1. Exact competitor + topic match
    cursor.execute("""
        SELECT * FROM scan_memory
        WHERE LOWER(competitor) = LOWER(?) AND LOWER(topic) = LOWER(?)
        ORDER BY timestamp DESC, id DESC LIMIT 1
    """, (clean_comp, clean_topic))
    row = cursor.fetchone()
    topic_match = row is not None

    # 2. Fallback: same competitor, any topic
    if row is None:
        cursor.execute("""
            SELECT * FROM scan_memory
            WHERE LOWER(competitor) = LOWER(?)
            ORDER BY timestamp DESC, id DESC LIMIT 1
        """, (clean_comp,))
        row = cursor.fetchone()

    conn.close()

    if row:
        # A row written by an older build may not hold valid JSON. Recall is a
        # nice-to-have, so a bad row degrades to "no prior gaps" instead of
        # taking down the scan that is merely reading it.
        try:
            prior_gap_report = json.loads(row["gap_report"])
        except (TypeError, ValueError):
            logger.warning(
                f"scan_memory row id={row['id']} has an unparseable gap_report; treating it as empty."
            )
            prior_gap_report = []

        return {
            "id": row["id"],
            "topic": row["topic"],
            "competitor": row["competitor"],
            "timestamp": row["timestamp"],
            "gap_report": prior_gap_report,
            "executive_summary": row["executive_summary"],
            "topic_match": topic_match
        }
    return None

def save_scan_memory(topic: str, competitor: str, gap_report: List[Dict[str, Any]], executive_summary: str):
    """Writes a new completed scan record to SQLite database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO scan_memory (topic, competitor, timestamp, gap_report, executive_summary)
        VALUES (?, ?, ?, ?, ?)
    """, (topic, competitor, now_str, json.dumps(gap_report), executive_summary))

    conn.commit()
    conn.close()

def describe_prior_gap(prior_gaps: Any) -> str:
    """
    Extracts a human-readable gap description from a stored gap report.

    Rows written before the gap report became deterministic hold a plain list of
    strings (the LLM used to author them), and some hold an empty list or a bare
    string. A deployed database therefore contains several shapes at once, so
    every one is tolerated here rather than assumed away — the previous
    `prior_gaps[0].get(...)` raised AttributeError on legacy string rows and
    failed the entire scan with a 500.
    """
    fallback = "Thin coverage"

    if isinstance(prior_gaps, dict):
        prior_gaps = [prior_gaps]
    if isinstance(prior_gaps, str):
        return prior_gaps.strip() or fallback
    if not isinstance(prior_gaps, list) or not prior_gaps:
        return fallback

    first = prior_gaps[0]
    if isinstance(first, dict):
        desc = first.get("gap") or first.get("description") or ""
        return str(desc).strip() or fallback
    return str(first).strip() or fallback


def compute_memory_delta(prior_memory: Optional[Dict[str, Any]], competitor: str, current_gap_report: List[Dict[str, Any]], current_observations_count: int) -> str:
    """
    Computes a string delta comparing the prior gap report with the *current* scan's findings.

    Must be called after the scan completes — current_gap_report is the gap report produced by
    this run, not the prior one.
    """
    if not prior_memory:
        return f"First recorded scan for {competitor}. Baseline established in long-term store."

    prior_time = prior_memory["timestamp"]
    prior_gap_desc = describe_prior_gap(prior_memory.get("gap_report"))

    scope_note = ""
    if prior_memory.get("topic_match") is False:
        scope_note = f" (prior record was for a different topic: '{prior_memory['topic']}')"

    # Check whether this competitor is still flagged in the current run's gap report
    is_currently_gapped = any(
        str(g.get("entity", "")).lower() == competitor.lower()
        for g in current_gap_report if isinstance(g, dict)
    )

    if not is_currently_gapped:
        return (
            f"Prior scan ({prior_time}) flagged '{prior_gap_desc}' for {competitor}{scope_note}; "
            f"current scan gathered {current_observations_count} grounded signals — coverage gap resolved."
        )
    return (
        f"Prior scan ({prior_time}) flagged '{prior_gap_desc}' for {competitor}{scope_note}; "
        f"current scan continues to show thin signal density."
    )
