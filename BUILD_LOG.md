# IntelPulse — Overnight Build Log

Unattended build session. Started 2026-08-23 ~01:00 local.
Four phases, strict priority order: LangGraph migration → frontend integration → UI redesign → eval harness.

Every entry records what was done, what was decided and why, and the commit that
holds the last known-working state.

---

## Environment findings (recorded before any work started)

These are facts about the repo that differ from the build brief. Decisions taken
in response are noted; nothing here was guessed at silently.

| Brief said | Actual | Decision |
| :--- | :--- | :--- |
| "`search_web` (Tavily fallback)" | There is **no Tavily integration and no `search_web` tool.** The real web fallback is the `ddgs` (ex-`duckduckgo-search`) search used as tier 3 inside `tools/patent_tool.py`. | Wire the fallback layer to the fallback that actually exists (`ddgs` web search) rather than adding a Tavily dependency and an API key the team does not have. A `WEB_FALLBACK` adapter is used so Tavily can be dropped in later by changing one function. |
| skill `ui-ux-pro` | installed skill is **`ui-ux-pro-max`** | Use `ui-ux-pro-max` (Phase 3). |
| RuntimeX is a separate repo | `https://github.com/VRD-07/RuntimeX` **is this repo**; `vintage-ui-update` is a branch of it | Phase 2 = merge/adopt the `vintage-ui-update` frontend into this working tree, not a cross-repo integration. |
| Deploy + smoke-test on Render/Vercel each phase | No `render.yaml` / `vercel.json` in the repo; deploys are dashboard-configured. **This session has no Render/Vercel credentials and cannot trigger or verify a deploy.** | Push every commit to `origin` (which is what triggers auto-deploy if it is configured on the dashboards) and verify end-to-end against a **real local server** instead. Deploy verification is listed in the morning checklist as a human step. This is a genuine limitation, not a skipped step — see "Morning checklist". |
| LangGraph in use | not installed | Installed `langgraph 1.2.11`, `langgraph-checkpoint-sqlite 3.1.1`. Added to `backend/requirements.txt`. |

---

## Phase 0 — Baseline

**Goal:** start from a verified-working, committed state (hard rule #1).

Carried in from the previous session and already verified before this build began:
patent-source migration (PatentsView is retired — DNS gone) to a 3-tier
India-first ladder, plus two new evidence sources (Hugging Face model traction,
Hacker News) and enriched GitHub metadata. 17 files.

Verification at baseline (all re-run, not assumed):

- `test_patent_parsers.py` — PASSED (offline parser fixtures)
- `test_audit_tools.py` — PASSED, all 7 tools honour the `{text, items, source_type}` contract
- `verify_e2e.py` — PASSED against a live server: 27 findings, 13/13 `step_start`↔`step_complete` paired, every section matches its flat array, 0 non-http URLs
- `npm run build` — clean, 1558 modules

**State: committed and pushed as the baseline revert point.**

---
