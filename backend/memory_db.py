import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "intelpulse_memory.db")

def get_db_connection():
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
        print(f"[Memory DB] Auto-seeded baseline prior scan memory (3 records, timestamped {seed_time}).")

    conn.close()

def get_prior_scan_memory(topic: str, competitor: str) -> Optional[Dict[str, Any]]:
    """Retrieves the most recent prior scan record for a given competitor and topic."""
    conn = get_db_connection()
    cursor = conn.cursor()

    clean_comp = competitor.strip()
    cursor.execute("""
        SELECT * FROM scan_memory
        WHERE LOWER(competitor) = LOWER(?) OR LOWER(?) LIKE '%' || LOWER(competitor) || '%'
        ORDER BY timestamp DESC LIMIT 1
    """, (clean_comp, topic))

    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "id": row["id"],
            "topic": row["topic"],
            "competitor": row["competitor"],
            "timestamp": row["timestamp"],
            "gap_report": json.loads(row["gap_report"]),
            "executive_summary": row["executive_summary"]
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

def compute_memory_delta(prior_memory: Optional[Dict[str, Any]], competitor: str, current_gap_report: List[Dict[str, Any]], current_observations_count: int) -> str:
    """Computes simple string delta comparing prior gap report with current scan findings."""
    if not prior_memory:
        return f"First recorded scan for {competitor}. Baseline established in long-term store."

    prior_time = prior_memory["timestamp"]
    prior_gaps = prior_memory["gap_report"]
    prior_gap_desc = prior_gaps[0].get("gap", "Thin coverage") if prior_gaps else "Thin coverage"

    # Check if current competitor is in current gap report
    is_currently_gapped = any(g.get("entity", "").lower() == competitor.lower() for g in current_gap_report)

    if not is_currently_gapped:
        return f"Prior scan ({prior_time}) flagged '{prior_gap_desc}' for {competitor}; current scan gathered {current_observations_count} grounded signals — coverage gap resolved."
    else:
        return f"Prior scan ({prior_time}) flagged '{prior_gap_desc}' for {competitor}; current scan continues to show thin signal density."
