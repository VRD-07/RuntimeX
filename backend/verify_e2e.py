"""End-to-end verification against a running server.

Drives /api/scan/stream exactly the way the browser does, then asserts the
invariants that the UI depends on and that the earlier bugs violated:

  * NDJSON parses line by line, and every step_start is paired with a step_complete
  * every SECTION_ORDER source type reaches structured_output.sections
  * each section bucket matches its flat top-level array (the reddit_posts bug)
  * every item carries a real http(s) URL (citation integrity)
  * /api/chat accepts and uses the new context_* arrays

Usage:
    python verify_e2e.py [base_url]
"""

import json
import sys
import urllib.error
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8077").rstrip("/")

# Must mirror SECTION_ORDER / SECTION_RESPONSE_KEYS in agent_brain.py.
RESPONSE_KEYS = {
    "news": "news",
    "research": "papers",
    "patents": "patents",
    "github": "github_repos",
    "reddit": "reddit_posts",
    "models": "hf_models",
    "hackernews": "hn_posts",
}

failures = []


def check(label, ok, detail=""):
    print(f"  {'OK  ' if ok else 'FAIL'} {label}" + (f" -- {detail}" if detail else ""))
    if not ok:
        failures.append(label)
    return ok


def post(path, payload, timeout=600):
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return urllib.request.urlopen(req, timeout=timeout)


def stream_scan():
    print(f"POST {BASE}/api/scan/stream")
    payload = {
        "topic": "Indian large language models",
        # A comma-separated STRING, not an array.
        "competitors": "Sarvam AI, AI4Bharat",
        "max_items": 3,
        "max_steps": 18,
    }
    events, buffer, bad_lines = [], "", 0
    with post("/api/scan/stream", payload) as resp:
        check("stream content-type is NDJSON", "x-ndjson" in resp.headers.get("content-type", ""),
              resp.headers.get("content-type", ""))
        for raw in resp:
            buffer += raw.decode("utf-8", errors="replace")
            lines = buffer.split("\n")
            buffer = lines.pop()
            for line in lines:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    bad_lines += 1
                    continue
                events.append(event)
                etype = event.get("type")
                if etype == "step_start":
                    print(f"    -> {event.get('tool') or event.get('label') or 'step'}")
                elif etype == "error":
                    print(f"    !! error event: {str(event)[:300]}")
    if buffer.strip():
        try:
            events.append(json.loads(buffer))
        except json.JSONDecodeError:
            bad_lines += 1

    check("no unparseable NDJSON lines", bad_lines == 0, f"{bad_lines} bad line(s)")
    starts = [e for e in events if e.get("type") == "step_start"]
    completes = [e for e in events if e.get("type") == "step_complete"]
    check("step_start / step_complete paired", len(starts) == len(completes),
          f"{len(starts)} starts vs {len(completes)} completes")
    check("at least one tool step ran", len(starts) > 0, f"{len(starts)} steps")

    finals = [e for e in events if e.get("type") == "final_complete"]
    check("exactly one final_complete", len(finals) == 1, f"{len(finals)}")
    return finals[-1] if finals else None


def verify_payload(final, label):
    print(f"\nPayload invariants ({label})")
    sections = (final.get("structured_output") or {}).get("sections") or []
    check("sections is a list", isinstance(sections, list), type(sections).__name__)
    by_type = {s.get("source_type"): (s.get("items") or []) for s in sections if isinstance(s, dict)}

    missing = [t for t in RESPONSE_KEYS if t not in by_type]
    check("every source type present in sections", not missing, f"missing {missing}")

    for source_type, response_key in RESPONSE_KEYS.items():
        section_items = by_type.get(source_type, [])
        flat_items = final.get(response_key)
        check(f"flat key '{response_key}' exists", isinstance(flat_items, list),
              type(flat_items).__name__)
        check(f"'{source_type}' section == '{response_key}' array",
              len(section_items) == len(flat_items or []),
              f"{len(section_items)} vs {len(flat_items or [])}")

    total, bad_url, bad_meta = 0, [], []
    for source_type, items in by_type.items():
        for item in items:
            total += 1
            url = (item.get("url") or "").strip()
            if not url.startswith(("http://", "https://")):
                bad_url.append(f"{source_type}: {url!r}")
            if not (item.get("title") or "").strip() or not (item.get("source_name") or "").strip():
                bad_meta.append(f"{source_type}: {str(item)[:80]}")
    check("every item has an http(s) URL", not bad_url, "; ".join(bad_url[:4]))
    check("every item has title + source_name", not bad_meta, "; ".join(bad_meta[:4]))
    print(f"    {total} findings across {len([t for t in by_type if by_type[t]])} populated source types")
    for source_type in RESPONSE_KEYS:
        print(f"      {source_type:<11} {len(by_type.get(source_type, [])):>2}")

    takeaway = (final.get("structured_output") or {}).get("executive_takeaway") or ""
    check("executive_takeaway present", len(takeaway.strip()) > 40, f"{len(takeaway)} chars")
    gap = final.get("gap_report")
    check("gap_report present", gap is not None, type(gap).__name__)
    return by_type


def verify_chat(by_type):
    print(f"\nPOST {BASE}/api/chat (new context arrays)")
    payload = {
        "question": "Which competitor shows the strongest real-world adoption, and what patent coverage did we actually retrieve?",
        "chat_history": [],
        "context_research": by_type.get("research", []),
        "context_competitors": by_type.get("news", []),
        "context_patents": by_type.get("patents", []),
        "context_github": by_type.get("github", []),
        "context_reddit": by_type.get("reddit", []),
        "context_models": by_type.get("models", []),
        "context_hackernews": by_type.get("hackernews", []),
    }
    try:
        with post("/api/chat", payload, timeout=180) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as exc:
        check("chat returns 200", False, f"HTTP {exc.code}: {exc.read()[:200]!r}")
        return
    answer = data.get("answer") or ""
    check("chat returns an answer", len(answer.strip()) > 40, f"{len(answer)} chars")
    print(f"    {answer.strip()[:400]}")


def main():
    print("=" * 70)
    final = stream_scan()
    if not final:
        print("\nNo final_complete event; cannot verify payload.")
        return 1
    by_type = verify_payload(final, "stream")

    print(f"\nPOST {BASE}/api/scan (buffered path)")
    try:
        with post("/api/scan", {"topic": "Indian large language models",
                                "competitors": "Sarvam AI",
                                "max_items": 2, "max_steps": 8}) as resp:
            buffered = json.load(resp)
        verify_payload(buffered, "buffered")
    except urllib.error.HTTPError as exc:
        check("buffered scan returns 200", False, f"HTTP {exc.code}: {exc.read()[:200]!r}")

    verify_chat(by_type)

    print("\n" + "=" * 70)
    if failures:
        print(f"FAILED -- {len(failures)} check(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASSED -- end-to-end contract holds across all seven sources.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
