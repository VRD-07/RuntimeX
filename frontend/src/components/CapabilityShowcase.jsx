import React from 'react';
import {
  X,
  Award,
  Brain,
  Wrench,
  Users,
  Database,
  GitBranch,
  ClipboardCheck,
  Activity,
  ArrowRight,
  Zap,
  Loader2,
} from 'lucide-react';

/**
 * Judge-facing capability showcase.
 *
 * A slide-over that maps each hackathon requirement to the place in this app
 * where it actually runs, so a reviewer never has to guess which panel proves
 * which claim. Everything here is descriptive except the chaos trigger, which
 * fires a real scan against the backend's chaos_mode=tool_failure parameter.
 *
 * The evaluation numbers are the real output of `backend/eval_and_trace.py`,
 * copied from the committed `eval_report.md`. They are stated as a dated
 * measurement rather than read live, because the report is generated at the
 * repository root by a Python harness and is not part of the frontend bundle.
 */

// Straight from eval_report.md — two live scans over the same input,
// topic "Indian language AI models", competitor "Sarvam AI", max_items=3.
const EVAL_ROWS = [
  { metric: 'Latency (s)', normal: '25.5', chaos: '20.1' },
  { metric: 'Tool calls', normal: '7', chaos: '7' },
  { metric: 'Findings retrieved', normal: '21', chaos: '21' },
  { metric: 'Unrecovered errors', normal: '0', chaos: '0' },
  { metric: 'Recovered tier failures', normal: '0', chaos: '2' },
  { metric: 'Tools returning nothing', normal: '0', chaos: '0' },
  { metric: 'Patent records', normal: '3', chaos: '3' },
  { metric: 'Task success', normal: 'PASS', chaos: 'PASS' },
];

function EvalTable() {
  return (
    <div className="mt-3 overflow-hidden rounded-xl border border-white/10 bg-black/30 backdrop-blur-sm">
      <table className="w-full text-left font-mono text-[11px]">
        <thead className="border-b border-white/10 text-slate-400">
          <tr>
            <th className="px-3 py-2 font-semibold">Metric</th>
            <th className="px-3 py-2 text-right font-semibold">Normal</th>
            <th className="px-3 py-2 text-right font-semibold">chaos_mode</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/[0.06]">
          {EVAL_ROWS.map((r) => {
            // The two rows that carry the argument: the failure was injected and
            // recovered, and the task still completed either way.
            const key = r.normal !== r.chaos || r.metric === 'Task success';
            return (
              <tr key={r.metric} className={key ? 'bg-sky-400/[0.06]' : ''}>
                <td className="px-3 py-1.5 text-slate-300">{r.metric}</td>
                <td className="px-3 py-1.5 text-right text-slate-100">{r.normal}</td>
                <td className={`px-3 py-1.5 text-right ${key ? 'font-bold text-sky-200' : 'text-slate-100'}`}>
                  {r.chaos}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/**
 * `onJump` scrolls to and flashes a real dashboard panel.
 * `onRunChaos` launches a real adversarial scan.
 */
export default function CapabilityShowcase({ open, onClose, onJump, onRunChaos, chaosRunning, chaosArmed }) {
  const CAPABILITIES = [
    {
      icon: Brain,
      title: '1. Agentic Reasoning (ReAct)',
      body:
        'Every retrieval step is a full Thought → Action → Observation cycle: the Field Agent states why it is calling a tool, names the exact tool and arguments, then records the raw result it got back — and the next step is planned from that observation, not from a fixed script.',
      jump: { id: 'trace-panel', label: 'Open the reasoning trace' },
    },
    {
      icon: Wrench,
      title: '2. Tool Usage & Grounding',
      body:
        'Seven live tools are wired in — Semantic Scholar, web news, patents, GitHub, Reddit, Hugging Face and Hacker News. Every card on the board comes from a real Observation and carries its own source name, date and outbound URL, so each claim can be clicked back to its origin; when a source returns nothing the agent reports it as empty and when it is unreachable it reports it as unavailable, rather than inventing filler.',
      jump: { id: 'findings-board', label: 'Open the findings board' },
    },
    {
      icon: Users,
      title: '3. Multi-Agent Architecture',
      body:
        'Three roles with hard boundaries: the Field Agent only retrieves and may never interpret, the Analyst Agent only synthesizes from observations already collected and may never fetch, and the Orchestrator plans the fan-out, spots coverage gaps and dispatches a second retrieval round. Every trace row is tagged with the agent that produced it.',
      jump: { id: 'trace-panel', label: 'See the per-agent step labels' },
    },
    {
      icon: Database,
      title: '4. Context & Memory Management',
      body:
        'Findings are compacted into a per-source context the Analyst and the Q&A panel both read from, and each run writes its gap report to SQLite keyed by competitor and topic. On the next scan of the same target the agent recalls that record first and reports the delta against it, so a repeat scan says what changed rather than starting from zero.',
      jump: { id: 'memory-panel', label: 'Open the memory trace' },
    },
    {
      icon: GitBranch,
      title: '5. Agent Framework',
      body:
        'Orchestration is explicit rather than delegated to a graph library: typed state flows between agents, routing decides which tools each competitor needs, replanning issues a gap-fill round, and a step budget bounds the loop — the same state/routing/replanning contract LangGraph provides. Fault injection is built into that loop, so the failure path is part of the design and not an afterthought.',
      chaos: true,
    },
    {
      icon: ClipboardCheck,
      title: '6. Evaluation',
      body:
        'backend/eval_and_trace.py drives the agent in-process twice over identical input — once normally, once with the patent tool deliberately broken — and measures latency, tool calls, findings, unrecovered errors, recovered tier failures, token usage and task success, exiting non-zero unless both runs pass. Task success is the whole job, not an HTTP 200: the scan finished, produced grounded findings, lost no tool unrecovered, and the analyst wrote a real takeaway.',
      table: true,
    },
    {
      icon: Activity,
      title: '7. Tracing & Observability',
      body:
        'The trace panel streams live over NDJSON: one row per step with its timestamp, the acting agent, the tool called and the observation returned, expandable to the full text. Gemini token counts are read from the API\'s own usage_metadata and accumulated per run, and deliberate failures are tagged step_type: "chaos" so an injected fault can never be misread as a real outage. The before/after column below is that instrumentation applied to a controlled failure.',
      table: true,
      note:
        'In the run above the Gemini key was past its free-tier daily quota, so both scans fell through to the deterministic analyst and there was no successful LLM call to count — the token instrumentation is live, the counter is honestly zero.',
    },
  ];

  return (
    <>
      {/* Scrim: click-away close, and it dims the board so the panel reads as foreground. */}
      <div
        onClick={onClose}
        className={`fixed inset-0 z-[60] bg-slate-950/70 backdrop-blur-sm transition-opacity duration-300 ${
          open ? 'opacity-100' : 'pointer-events-none opacity-0'
        }`}
        aria-hidden="true"
      />

      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Capability showcase"
        className={`fixed right-0 top-0 z-[61] flex h-full w-full max-w-xl flex-col border-l border-white/10 bg-slate-950/80 backdrop-blur-2xl transition-transform duration-300 ease-out ${
          open ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <header className="flex items-start justify-between gap-4 border-b border-white/10 px-6 py-5">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-sky-500/90 p-2.5 text-white glass-edge">
              <Award className="h-5 w-5" />
            </div>
            <div>
              <h2 className="font-serif text-lg font-bold tracking-tight text-slate-50">Capability Showcase</h2>
              <p className="font-sans text-xs text-slate-400">
                Each requirement, and where it actually runs in this dashboard
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close capability showcase"
            className="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-white/10 hover:text-white"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="flex-1 space-y-4 overflow-y-auto px-6 py-5">
          {CAPABILITIES.map((cap) => {
            const Icon = cap.icon;
            return (
              <section
                key={cap.title}
                className="rounded-2xl border border-white/10 bg-white/[0.05] p-4 backdrop-blur-xl glass-edge"
              >
                <h3 className="flex items-center gap-2 font-serif text-sm font-semibold text-slate-50">
                  <Icon className="h-4 w-4 shrink-0 text-sky-300" />
                  {cap.title}
                </h3>
                <p className="mt-2 font-sans text-xs leading-relaxed text-slate-300">{cap.body}</p>

                {cap.jump && (
                  <button
                    onClick={() => onJump(cap.jump.id)}
                    className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-sky-400/40 bg-sky-400/10 px-3 py-1.5 font-mono text-[11px] font-semibold text-sky-200 transition-colors hover:bg-sky-400/20"
                  >
                    {cap.jump.label}
                    <ArrowRight className="h-3 w-3" />
                  </button>
                )}

                {cap.chaos && (
                  <div className="mt-3 space-y-2">
                    <button
                      onClick={onRunChaos}
                      disabled={chaosRunning}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-rose-400/45 bg-rose-500/15 px-3 py-1.5 font-mono text-[11px] font-bold text-rose-100 transition-colors hover:bg-rose-500/25 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {chaosRunning ? (
                        <>
                          <Loader2 className="h-3 w-3 animate-spin" />
                          Adversarial scan running…
                        </>
                      ) : (
                        <>
                          <Zap className="h-3 w-3" />
                          Trigger live chaos scan (tool_failure)
                        </>
                      )}
                    </button>
                    <p className="font-mono text-[10px] leading-relaxed text-slate-400">
                      Runs a real scan with <span className="text-rose-300">chaos_mode=tool_failure</span>. The
                      authoritative patent tiers are forced to raise; watch the trace fill with rose
                      <span className="text-rose-300"> CHAOS</span> rows and the scan still complete from the
                      fallback tier.
                      {chaosArmed && !chaosRunning && (
                        <span className="mt-1 block font-bold text-rose-300">
                          Last scan ran with fault injection active.
                        </span>
                      )}
                    </p>
                  </div>
                )}

                {cap.table && <EvalTable />}

                {cap.note && (
                  <p className="mt-2 border-l-2 border-amber-400/50 pl-3 font-sans text-[11px] leading-relaxed text-amber-200/90">
                    {cap.note}
                  </p>
                )}
              </section>
            );
          })}
        </div>

        <footer className="border-t border-white/10 px-6 py-3 font-mono text-[10px] text-slate-500">
          Numbers from <span className="text-slate-300">eval_report.md</span>, generated by{' '}
          <span className="text-slate-300">backend/eval_and_trace.py</span>. Re-run it to regenerate.
        </footer>
      </aside>
    </>
  );
}
