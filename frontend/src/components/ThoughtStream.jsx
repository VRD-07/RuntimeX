import React, { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Brain, CheckCircle2, ChevronRight, Loader2 } from 'lucide-react';

/**
 * The thought process, parked directly beneath the scan controls.
 *
 * Placement is the point: the ReAct loop is the thing being demonstrated, so it
 * sits next to the button that starts it rather than below the results, and it
 * auto-follows the newest step as the stream arrives. One line per step by
 * default — click a row for the full Thought / Action / Observation.
 */

// "search_news(query='Sarvam AI funding')" -> "search_news · Sarvam AI funding"
export function summarizeStep(step) {
  const action = (step.action || '').trim();
  if (!action) return (step.thought || 'Reasoning step').slice(0, 90);
  const match = action.match(/^([\w.]+)\s*\((.*)\)$/s);
  if (!match) return action.slice(0, 90);
  const tool = match[1].split('.').pop();
  const args = match[2].replace(/\w+\s*=\s*/g, '').replace(/['"]/g, '').trim();
  return args ? `${tool} · ${args.slice(0, 58)}` : tool;
}

/**
 * A step's role badge. Chaos steps are labelled explicitly so a deliberately
 * injected failure can never be mistaken for a real one.
 */
export function stepBadge(step) {
  if (step.step_type === 'chaos' || step.chaos) return { label: 'CHAOS', className: 'bg-rose-600/90 text-white' };
  if (step.step_type === 'memory_recall') return { label: 'MEMORY', className: 'bg-ochre text-ink' };
  if (step.agent_role === 'Analyst Agent') return { label: 'ANALYST', className: 'bg-plum text-white' };
  if (step.agent_role === 'Orchestrator') return { label: 'ORCHESTR', className: 'bg-teal-deep text-white' };
  return { label: 'FIELD', className: 'bg-clay text-white' };
}

export default function ThoughtStream({ trace = [], visibleCount, loading, flash = '' }) {
  const [openStep, setOpenStep] = useState(null);
  const scroller = useRef(null);
  const steps = trace.slice(0, visibleCount);

  // Follow the stream while it is running, but stop fighting the user once the
  // scan is done and they start reading back through it.
  useEffect(() => {
    if (!loading || !scroller.current) return;
    scroller.current.scrollTop = scroller.current.scrollHeight;
  }, [steps.length, loading]);

  return (
    <section
      id="trace-panel"
      className={`glass-panel flex min-h-0 flex-1 flex-col overflow-hidden transition-shadow duration-300${flash}`}
    >
      <header className="flex shrink-0 items-center gap-2 border-b border-ink/10 px-3 py-2">
        <Brain className="h-3.5 w-3.5 shrink-0 text-clay" />
        <div className="min-w-0 flex-1">
          <h2 className="font-sans text-[12px] font-bold leading-tight text-ink">Thought Process</h2>
          <p className="truncate font-hand text-[13px] leading-tight text-moss">
            thought → action → observation, live
          </p>
        </div>
        <span className="shrink-0 rounded-md bg-ink/[0.06] px-1.5 py-0.5 font-mono text-[9px] font-bold text-ink/60">
          {trace.length} steps
        </span>
      </header>

      <div ref={scroller} className="thin-scroll min-h-0 flex-1 overflow-y-auto px-2 py-1.5">
        {steps.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-1.5 px-4 text-center">
            <Brain className="h-5 w-5 text-ink/20" />
            <p className="font-mono text-[10px] leading-relaxed text-ink/40">
              The reasoning loop prints here the moment a scan starts.
            </p>
          </div>
        ) : (
          <ol className="space-y-1">
            <AnimatePresence initial={false}>
              {steps.map((step, idx) => {
                const badge = stepBadge(step);
                const isOpen = openStep === idx;
                const done = !!step.observation || !!step.content;
                return (
                  <motion.li
                    key={`${step.step ?? idx}-${idx}`}
                    layout="position"
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
                    className="overflow-hidden rounded-lg border border-white/60 bg-white/45"
                  >
                    <button
                      onClick={() => setOpenStep(isOpen ? null : idx)}
                      className="flex w-full items-center gap-1.5 px-1.5 py-1 text-left transition-colors hover:bg-white/70"
                    >
                      <motion.span animate={{ rotate: isOpen ? 90 : 0 }} transition={{ duration: 0.18 }}>
                        <ChevronRight className="h-3 w-3 shrink-0 text-ink/35" />
                      </motion.span>

                      <span className="w-4 shrink-0 font-mono text-[9px] text-ink/40">
                        {String(step.step ?? idx + 1).padStart(2, '0')}
                      </span>

                      <span
                        className={`${badge.className} w-[58px] shrink-0 rounded px-1 py-[1px] text-center font-mono text-[8px] font-bold tracking-wide`}
                      >
                        {badge.label}
                      </span>

                      <span className="min-w-0 flex-1 truncate font-mono text-[10px] text-ink/75">
                        {summarizeStep(step)}
                      </span>

                      {done ? (
                        <CheckCircle2 className="h-3 w-3 shrink-0 text-teal-deep" />
                      ) : (
                        <Loader2 className="h-3 w-3 shrink-0 animate-spin text-clay" />
                      )}
                    </button>

                    <AnimatePresence initial={false}>
                      {isOpen && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.22, ease: 'easeOut' }}
                          className="overflow-hidden bg-ink/[0.04]"
                        >
                          <div className="space-y-1.5 px-2.5 py-2 font-mono text-[10px] leading-relaxed">
                            {step.thought && (
                              <p>
                                <span className="font-bold text-moss">Thought </span>
                                <span className="text-ink/75">{step.thought}</span>
                              </p>
                            )}
                            {step.action && (
                              <p>
                                <span className="font-bold text-clay">Action </span>
                                <span className="break-all text-ink/75">{step.action}</span>
                              </p>
                            )}
                            {step.observation && (
                              <p>
                                <span className="font-bold text-teal-deep">Observation </span>
                                <span className="text-ink/70">{String(step.observation).slice(0, 520)}</span>
                              </p>
                            )}
                            {step.content && (
                              <p>
                                <span className="font-bold text-ochre-deep">Recall </span>
                                <span className="text-ink/75">{step.content}</span>
                              </p>
                            )}
                            {step.delta && (
                              <p>
                                <span className="font-bold text-ochre-deep">Delta </span>
                                <span className="text-ink/75">{step.delta}</span>
                              </p>
                            )}
                            <p className="text-ink/35">
                              {step.agent_role || 'Field Agent'} · {step.ts || '--:--:--'}
                            </p>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </motion.li>
                );
              })}
            </AnimatePresence>
          </ol>
        )}
      </div>
    </section>
  );
}
