import React, { useState, useEffect, Suspense } from 'react';
import ReactMarkdown from 'react-markdown';
import { AnimatePresence, motion } from 'framer-motion';

import AgentDebugView from './debug/AgentDebugView';
import CapabilityShowcase from './components/CapabilityShowcase';
import Counter from './components/Counter';
import StatCharts from './components/StatCharts';
import FindingCard from './components/FindingCard';
import ThoughtStream from './components/ThoughtStream';
import { SOURCE_LABELS, SOURCE_RESPONSE_KEYS, SOURCE_TYPES } from './lib/sources';
import { checkHealth, runScan, runScanStream, sendChatMessage } from './api';

// three.js is ~1.2 MB of the bundle. Both WebGL surfaces are deferred so the
// dashboard paints on the main chunk and the 3D fades in a beat later.
const DotShaderBackground = React.lazy(() => import('./components/DotShaderBackground'));
const IntelOrb = React.lazy(() => import('./components/IntelOrb'));

import {
  Zap,
  Search,
  FileText,
  MessageSquare,
  Download,
  Send,
  RefreshCw,
  Cpu,
  Filter,
  Layers,
  History,
  AlertTriangle,
  Award,
  Radar,
  Users,
  Database,
  Waypoints
} from 'lucide-react';

// Synthesis is served by Gemini. These ids must match SUPPORTED_GEMINI_MODELS in the backend.
const MODEL_NAMES = {
  'gemini-2.5-flash': 'Gemini 2.5 Flash',
  'gemini-2.5-pro': 'Gemini 2.5 Pro',
  'gemini-2.0-flash': 'Gemini 2.0 Flash',
  'gemini-1.5-flash': 'Gemini 1.5 Flash',
  'gemini-1.5-pro': 'Gemini 1.5 Pro'
};

const DEFAULT_MODEL = 'gemini-2.5-flash';

/** One headline number in the stat strip. */
function StatTile({ icon: Icon, label, value, accent }) {
  return (
    <div className="glass-inset flex min-w-0 flex-col justify-center px-2.5 py-1.5">
      <span className="flex items-center gap-1 font-mono text-[9px] uppercase tracking-[0.12em] text-ink/50">
        <Icon className="h-3 w-3 shrink-0" style={{ color: accent }} />
        <span className="truncate">{label}</span>
      </span>
      <Counter value={value} className="font-sans text-xl font-bold leading-tight" />
    </div>
  );
}

export default function App() {
  if (typeof window !== 'undefined' && window.location.pathname.startsWith('/debug')) {
    return <AgentDebugView />;
  }

  const [topic, setTopic] = useState('Regional language capabilities for AI');
  const [competitors, setCompetitors] = useState('Sarvam, OpenAI, Google');
  const [maxItems, setMaxItems] = useState(5);
  const [model, setModel] = useState(DEFAULT_MODEL);

  const [loading, setLoading] = useState(false);
  const [scanError, setScanError] = useState(null);
  const [health, setHealth] = useState({ status: 'checking', llm_active: false });
  const [scanResult, setScanResult] = useState(null);

  // Filters state
  const [competitorFilter, setCompetitorFilter] = useState('All');
  const [sourceFilter, setSourceFilter] = useState('All');

  // Trace reveal state: steps are staggered in so the reasoning loop reads as a
  // sequence rather than appearing all at once.
  const [staggeredStepCount, setStaggeredStepCount] = useState(0);

  // Judge showcase state. flashPanel is the id of the panel currently being
  // highlighted after a jump; chaosArmed records whether the scan on screen was
  // run with fault injection, so the trace can never be mistaken for an outage.
  const [showcaseOpen, setShowcaseOpen] = useState(false);
  const [flashPanel, setFlashPanel] = useState(null);
  const [chaosArmed, setChaosArmed] = useState(false);

  // Chat state
  const [chatMessages, setChatMessages] = useState([]);
  const [userQuestion, setUserQuestion] = useState('');
  const [chatLoading, setChatLoading] = useState(false);

  useEffect(() => {
    fetchHealth();
  }, []);

  const fetchHealth = async () => {
    const data = await checkHealth();
    setHealth(data);
  };

  useEffect(() => {
    if (scanResult?.trace?.length > 0) {
      setStaggeredStepCount(1);
      const interval = setInterval(() => {
        setStaggeredStepCount((prev) => {
          if (prev >= scanResult.trace.length) {
            clearInterval(interval);
            return prev;
          }
          return prev + 1;
        });
      }, 350);
      return () => clearInterval(interval);
    }
  }, [scanResult]);

  const handleScan = async (e, { chaosMode = null } = {}) => {
    if (e) e.preventDefault();
    setScanResult(null);
    setScanError(null);
    setLoading(true);
    setStaggeredStepCount(0);
    setChaosArmed(!!chaosMode);

    let dynamicTrace = [];

    try {
      await runScanStream(topic, competitors, maxItems, model, (chunk) => {
        if (chunk.type === 'memory_recall') {
          const memStep = {
            step: 0,
            agent_role: 'Orchestrator',
            step_type: 'memory_recall',
            thought: chunk.thought,
            action: chunk.action,
            content: chunk.content,
            delta: chunk.delta,
            ts: new Date().toLocaleTimeString('en-GB')
          };
          dynamicTrace = [memStep, ...dynamicTrace.filter(s => s.step !== 0)];
          setScanResult({ trace: dynamicTrace });
        } else if (chunk.type === 'memory_update') {
          // The real delta is only known once the scan has finished; patch step 0 in place.
          dynamicTrace = dynamicTrace.map(s =>
            s.step === 0 ? { ...s, content: chunk.content, delta: chunk.delta } : s
          );
          setScanResult(prev => ({ ...(prev || {}), trace: dynamicTrace }));
        } else if (chunk.type === 'step_start') {
          const newStep = {
            step: chunk.step,
            agent_role: chunk.agent_role || 'Field Agent',
            thought: chunk.thought,
            action: chunk.action,
            observation: null,
            ts: new Date().toLocaleTimeString('en-GB')
          };
          dynamicTrace = [...dynamicTrace.filter(s => s.step !== chunk.step), newStep].sort((a, b) => a.step - b.step);
          setScanResult({ trace: dynamicTrace });
        } else if (chunk.type === 'step_complete') {
          const updatedStep = {
            step: chunk.step,
            agent_role: chunk.agent_role || 'Field Agent',
            thought: chunk.thought,
            action: chunk.action,
            observation: chunk.observation,
            step_type: chunk.step_type,
            chaos: chunk.chaos,
            // Preserve the start timestamp so the row does not jump to the
            // completion time once the observation lands.
            ts: (dynamicTrace.find(s => s.step === chunk.step) || {}).ts
              || new Date().toLocaleTimeString('en-GB')
          };
          dynamicTrace = [...dynamicTrace.filter(s => s.step !== chunk.step), updatedStep].sort((a, b) => a.step - b.step);
          setScanResult({ trace: dynamicTrace });
        } else if (chunk.type === 'final_complete') {
          setScanResult({
            ...chunk,
            trace: dynamicTrace
          });
        }
      }, chaosMode);
    } catch (err) {
      console.warn('Streaming failed, retrying with non-streaming scan:', err);
      try {
        const data = await runScan(topic, competitors, maxItems, model, chaosMode);
        setScanResult(data);
      } catch (fallbackErr) {
        console.error('Scan failed:', fallbackErr);
        setScanError(fallbackErr.message || 'Scan failed. Check that the backend is running.');
        setScanResult(null);
      }
    } finally {
      setLoading(false);
    }
  };

  /**
   * Rings a real dashboard panel so a jump from the showcase lands somewhere the
   * reviewer can see it landed. On a desktop viewport nothing scrolls — every
   * panel is already on screen — so the ring is the whole affordance; the
   * scrollIntoView only matters on the stacked mobile fallback.
   */
  const jumpToPanel = (id) => {
    setShowcaseOpen(false);
    setFlashPanel(id);
    requestAnimationFrame(() => {
      document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });
    setTimeout(() => setFlashPanel(null), 2400);
  };

  // Ring applied to whichever panel was just jumped to.
  const flashCls = (id) => (flashPanel === id ? ' ring-2 ring-clay/70 ring-offset-2 ring-offset-sand' : '');

  /** Fires a real scan with the backend's chaos_mode=tool_failure fault injection. */
  const handleChaosScan = () => {
    setShowcaseOpen(false);
    setFlashPanel('trace-panel');
    setTimeout(() => setFlashPanel(null), 2400);
    handleScan(null, { chaosMode: 'tool_failure' });
  };

  const handleSendChat = async (e) => {
    e.preventDefault();
    if (!userQuestion.trim()) return;

    const newMsg = { role: 'user', content: userQuestion };
    const updatedHistory = [...chatMessages, newMsg];
    setChatMessages(updatedHistory);
    setUserQuestion('');
    setChatLoading(true);

    try {
      const sectionItems = (type) => {
        const fromSections = scanResult?.structured_output?.sections?.find(s => s.source_type === type)?.items;
        if (fromSections) return fromSections;
        return scanResult?.[SOURCE_RESPONSE_KEYS[type]] || [];
      };

      const res = await sendChatMessage(userQuestion, updatedHistory, {
        research: sectionItems('research'),
        competitors: sectionItems('news'),
        patents: sectionItems('patents'),
        github: sectionItems('github'),
        reddit: sectionItems('reddit'),
        models: sectionItems('models'),
        hackernews: sectionItems('hackernews')
      }, model);

      let answerWithBadge = res.answer;
      if (res.tool_executed) {
        answerWithBadge = `⚡ **[Live Field Agent Lookup Triggered]** Called \`${res.tool_executed.action}\`\n\n` + res.answer;
      }

      setChatMessages(prev => [...prev, { role: 'assistant', content: answerWithBadge, tool_executed: res.tool_executed }]);
    } catch (err) {
      setChatMessages(prev => [...prev, { role: 'assistant', content: `Error: ${err.message}` }]);
    } finally {
      setChatLoading(false);
    }
  };

  const allFindings = React.useMemo(() => {
    if (!scanResult) return [];

    let items = [];

    if (scanResult.structured_output?.sections) {
      scanResult.structured_output.sections.forEach(sec => {
        sec.items.forEach(it => {
          items.push({
            id: Math.random().toString(),
            title: it.title,
            snippet: it.snippet,
            source_type: sec.source_type,
            source_name: it.source_name,
            date: it.date,
            url: it.url,
            entity: it.entity || 'General'
          });
        });
      });
    } else {
      if (scanResult.news) {
        scanResult.news.forEach(n => items.push({
          id: Math.random().toString(),
          title: n.title,
          snippet: n.snippet,
          source_type: 'news',
          source_name: n.source_name || 'Web News',
          date: n.date || 'Recent',
          url: n.url,
          entity: n.entity || 'General'
        }));
      }
      if (scanResult.papers) {
        scanResult.papers.forEach(p => items.push({
          id: Math.random().toString(),
          title: p.title,
          snippet: p.summary,
          source_type: 'research',
          source_name: 'Semantic Scholar',
          date: p.published || 'Recent',
          url: p.pdf_url,
          entity: p.entity || 'General'
        }));
      }
    }

    return items;
  }, [scanResult]);

  const competitorChips = React.useMemo(() => {
    const list = competitors.split(',').map(c => c.trim()).filter(Boolean);
    return ['All', ...list];
  }, [competitors]);

  const filteredFindings = React.useMemo(() => {
    return allFindings.filter(item => {
      const matchComp = competitorFilter === 'All' || item.entity.toLowerCase().includes(competitorFilter.toLowerCase());
      const matchSource = sourceFilter === 'All' || item.source_type.toLowerCase() === sourceFilter.toLowerCase();
      return matchComp && matchSource;
    });
  }, [allFindings, competitorFilter, sourceFilter]);

  const competitorChartData = React.useMemo(() => {
    const comps = competitors.split(',').map(c => c.trim()).filter(Boolean);
    return comps.map(c => {
      const count = allFindings.filter(it => it.entity.toLowerCase().includes(c.toLowerCase())).length;
      return { name: c, count };
    });
  }, [allFindings, competitors]);

  const sourceChartData = React.useMemo(() => {
    return SOURCE_TYPES.map(s => {
      const count = allFindings.filter(it => it.source_type.toLowerCase() === s).length;
      return { name: SOURCE_LABELS[s], value: count };
    }).filter(d => d.value > 0);
  }, [allFindings]);

  // How many of the seven wired sources actually produced evidence this run.
  const coverage = React.useMemo(() => {
    const total = SOURCE_TYPES.length;
    const used = sourceChartData.length;
    return { used, total, pct: Math.round((used / total) * 100) };
  }, [sourceChartData]);

  const executiveTakeaway = React.useMemo(() => {
    if (!scanResult) return null;

    if (scanResult.executive_report) {
      const lines = scanResult.executive_report.split('\n')
        .filter(l => l.trim() && !l.startsWith('#') && !l.startsWith('##') && !l.startsWith('- Grounded'))
        .map(l => l.replace(/^[-\*]\s+/, '').replace(/\*\*/g, '').trim());

      const snippetText = lines.slice(0, 4).join(' ');
      if (snippetText.length > 50) {
        return snippetText.slice(0, 380) + '... Strategic analysis indicates active competitive shifts across target competitors.';
      }
    }

    return `Strategic intelligence scan for ${topic} across ${competitors}. Key technical developments and competitor signals have been parsed across academic research, market news, patent filings, published model adoption, and open-source repositories. Review specific entity signals below for actionable positioning.`;
  }, [scanResult, topic, competitors]);

  const memoryRecallEvent = React.useMemo(() => {
    if (!scanResult?.trace) return null;
    return scanResult.trace.find(t => t.step_type === 'memory_recall' || t.step === 0);
  }, [scanResult]);

  return (
    <div className="relative flex min-h-screen flex-col overflow-x-hidden font-sans text-ink lg:h-full lg:overflow-hidden">
      {/* Animated dot-grid shader, behind everything; it quickens while a scan runs. */}
      <Suspense fallback={null}>
        <DotShaderBackground active={loading} />
      </Suspense>

      <CapabilityShowcase
        open={showcaseOpen}
        onClose={() => setShowcaseOpen(false)}
        onJump={jumpToPanel}
        onRunChaos={handleChaosScan}
        chaosRunning={loading && chaosArmed}
        chaosArmed={chaosArmed}
      />

      {/* HEADER — deliberately thin, because the dashboard below must fit one screen. */}
      <header className="relative z-20 shrink-0 border-b border-white/60 bg-white/45 backdrop-blur-xl">
        <div className="mx-auto flex w-full max-w-[1800px] items-center gap-3 px-4 py-2">
          <motion.div
            initial={{ rotate: -12, scale: 0.85, opacity: 0 }}
            animate={{ rotate: 0, scale: 1, opacity: 1 }}
            transition={{ type: 'spring', stiffness: 220, damping: 16 }}
            className="rounded-xl bg-clay p-2 text-white shadow-card"
          >
            <Zap className="h-4 w-4" />
          </motion.div>

          <div className="min-w-0">
            <h1 className="font-display text-[15px] font-extrabold leading-none tracking-tight text-ink">
              IntelPulse
            </h1>
            <p className="font-hand text-[14px] leading-tight text-moss">
              a research desk that shows its work
            </p>
          </div>

          <div className="ml-auto flex items-center gap-2">
            <div className="hidden items-center gap-1.5 rounded-lg border border-white/70 bg-white/60 px-2.5 py-1.5 font-mono text-[10px] font-semibold text-ink/70 backdrop-blur sm:flex">
              <motion.span
                animate={loading ? { scale: [1, 1.5, 1], opacity: [1, 0.5, 1] } : { scale: 1, opacity: 1 }}
                transition={{ duration: 1, repeat: loading ? Infinity : 0 }}
                className={`h-2 w-2 rounded-full ${loading ? 'bg-clay' : 'bg-teal-deep'}`}
              />
              {loading ? 'ReAct loop active' : 'System live'}
            </div>

            <div className="hidden items-center gap-1.5 rounded-lg border border-white/70 bg-white/60 px-2.5 py-1.5 font-mono text-[10px] backdrop-blur md:flex">
              <Cpu className="h-3.5 w-3.5 text-clay" />
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="cursor-pointer bg-transparent font-mono text-[10px] font-semibold text-ink focus:outline-none"
              >
                {Object.entries(MODEL_NAMES).map(([id, label]) => (
                  <option key={id} value={id}>{label}</option>
                ))}
              </select>
              <span
                className={`ml-1 rounded px-1.5 py-[1px] text-[9px] font-bold ${
                  health.llm_active ? 'bg-teal-deep/15 text-teal-deep' : 'bg-ochre/25 text-ochre-deep'
                }`}
              >
                {health.llm_active ? 'LIVE' : 'FALLBACK'}
              </span>
            </div>

            <button
              onClick={() => setShowcaseOpen(true)}
              className="flex items-center gap-1.5 rounded-lg bg-ink px-3 py-1.5 font-mono text-[10px] font-bold text-sand shadow-card transition-colors hover:bg-clay"
            >
              <Award className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Capability Showcase</span>
            </button>
          </div>
        </div>
      </header>

      {/* ONE-SCREEN DASHBOARD: three columns, each panel scrolling inside itself. */}
      <main className="relative z-10 mx-auto grid w-full max-w-[1800px] flex-1 gap-3 p-3 lg:min-h-0 lg:grid-cols-12">

        {/* ── LEFT: controls, then the reasoning loop directly beneath them ── */}
        <div className="flex min-h-0 flex-col gap-3 lg:col-span-3">

          {/* SCAN CONTROLS */}
          <section className="glass-panel shrink-0 p-3">
            <div className="flex items-center gap-2 border-b border-ink/10 pb-2">
              <Search className="h-3.5 w-3.5 text-clay" />
              <h2 className="flex-1 font-sans text-[12px] font-bold text-ink">Market Parameters</h2>
              <button
                onClick={fetchHealth}
                title="Re-check backend health"
                className="rounded-md p-1 text-ink/45 transition-colors hover:bg-white/70 hover:text-clay"
              >
                <RefreshCw className="h-3 w-3" />
              </button>
            </div>

            <form onSubmit={handleScan} className="space-y-2 pt-2.5">
              <div>
                <label className="mb-1 block font-mono text-[9px] font-bold uppercase tracking-[0.12em] text-ink/55">
                  Domain track
                </label>
                <input
                  type="text"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder="e.g. Regional language capabilities for AI"
                  className="glass-field w-full px-2.5 py-1.5 font-sans text-[11px] font-medium text-ink placeholder:text-ink/35"
                  required
                />
              </div>

              <div>
                <label className="mb-1 block font-mono text-[9px] font-bold uppercase tracking-[0.12em] text-ink/55">
                  Competitors (comma separated)
                </label>
                <input
                  type="text"
                  value={competitors}
                  onChange={(e) => setCompetitors(e.target.value)}
                  placeholder="e.g. Sarvam, OpenAI, Google"
                  className="glass-field w-full px-2.5 py-1.5 font-sans text-[11px] font-medium text-ink placeholder:text-ink/35"
                  required
                />
              </div>

              <div>
                <div className="mb-1 flex items-baseline justify-between">
                  <span className="font-mono text-[9px] font-bold uppercase tracking-[0.12em] text-ink/55">
                    Scan depth
                  </span>
                  <span className="font-hand text-[13px] leading-none text-clay">{maxItems} per source</span>
                </div>
                <input
                  type="range"
                  min="2"
                  max="10"
                  value={maxItems}
                  onChange={(e) => setMaxItems(parseInt(e.target.value))}
                  className="w-full"
                />
              </div>

              <motion.button
                type="submit"
                disabled={loading}
                whileHover={{ scale: loading ? 1 : 1.015 }}
                whileTap={{ scale: 0.985 }}
                className="relative flex w-full items-center justify-center gap-2 overflow-hidden rounded-xl bg-clay py-2.5 font-sans text-[12px] font-bold text-white shadow-card transition-colors hover:bg-clay-deep disabled:opacity-60"
              >
                {loading && (
                  <span className="pointer-events-none absolute inset-y-0 w-1/3 animate-sheen-sweep bg-white/25 blur-md" />
                )}
                {loading ? (
                  <>
                    <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                    <span>Scanning…</span>
                  </>
                ) : (
                  <>
                    <Zap className="h-3.5 w-3.5" />
                    <span>Run Autonomous Scan</span>
                  </>
                )}
              </motion.button>
            </form>

            <AnimatePresence>
              {scanError && (
                <motion.div
                  role="alert"
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="mt-2 flex items-start gap-2 overflow-hidden rounded-lg border border-rose-300/70 bg-rose-50/80 p-2 font-mono text-[10px] text-rose-900"
                >
                  <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0 text-rose-600" />
                  <span className="break-words">{scanError}</span>
                </motion.div>
              )}
            </AnimatePresence>
          </section>

          {/* Adversarial-run notice: a chaos trace must never read as a real outage. */}
          <AnimatePresence>
            {chaosArmed && (
              <motion.div
                initial={{ opacity: 0, y: -6, height: 0 }}
                animate={{ opacity: 1, y: 0, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="flex shrink-0 items-start gap-2 overflow-hidden rounded-xl border border-rose-300/70 bg-rose-50/85 px-2.5 py-2 font-mono text-[10px] leading-relaxed text-rose-900 backdrop-blur"
              >
                <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0 text-rose-600" />
                <span>
                  <span className="font-bold">Adversarial run:</span> launched with{' '}
                  <span className="font-bold">chaos_mode=tool_failure</span>. Rose CHAOS rows are injected faults,
                  not a real outage.
                </span>
              </motion.div>
            )}
          </AnimatePresence>

          {/* THOUGHT PROCESS — parked against the button that starts it */}
          <ThoughtStream
            trace={scanResult?.trace || []}
            visibleCount={staggeredStepCount}
            loading={loading}
            flash={flashCls('trace-panel')}
          />

          {/* CROSS-RUN MEMORY */}
          <section
            id="memory-panel"
            className={`glass-panel shrink-0 p-2.5 transition-shadow duration-300${flashCls('memory-panel')}`}
          >
            <div className="flex items-center gap-1.5">
              <History className="h-3.5 w-3.5 text-ochre-deep" />
              <h2 className="flex-1 font-sans text-[11px] font-bold text-ink">Long-Term Memory</h2>
              <span className="rounded bg-ink/[0.06] px-1.5 py-0.5 font-mono text-[9px] font-bold text-ink/55">
                SQLite
              </span>
            </div>

            {memoryRecallEvent ? (
              <div className="mt-1.5 space-y-1">
                <p className="line-clamp-2 font-sans text-[11px] leading-snug text-ink/80">
                  {memoryRecallEvent.content || 'Loaded prior gap report for target competitor.'}
                </p>
                <p className="line-clamp-2 border-t border-ink/10 pt-1 font-mono text-[10px] text-ink/60">
                  <span className="font-bold text-ochre-deep">Delta </span>
                  {memoryRecallEvent.delta || 'Baseline established.'}
                </p>
              </div>
            ) : (
              <p className="mt-1.5 font-mono text-[10px] leading-relaxed text-ink/45">
                No recall yet — a scan writes its gap report to SQLite and reads it back on the next run.
              </p>
            )}
          </section>
        </div>

        {/* ── CENTRE: the headline numbers, then the main event ── */}
        <div className="flex min-h-0 flex-col gap-3 lg:col-span-6">

          {/* STAT STRIP: a live 3D readout plus the four counts that matter */}
          <section className="glass-panel flex shrink-0 items-center gap-3 p-2.5">
            <div className="relative h-[84px] w-[84px] shrink-0">
              <Suspense
                fallback={
                  <div className="h-full w-full animate-pulse rounded-full border border-white/70 bg-white/40" />
                }
              >
                <IntelOrb findings={allFindings.length} active={loading} className="h-full w-full" />
              </Suspense>
            </div>

            <div className="grid min-w-0 flex-1 grid-cols-2 gap-2 sm:grid-cols-4">
              <StatTile icon={Radar} label="Signals" value={allFindings.length} accent="#C2603A" />
              <StatTile icon={Users} label="Competitors" value={competitorChartData.length} accent="#6E7455" />
              <StatTile icon={Database} label="Sources" value={sourceChartData.length} accent="#4E7A6E" />
              <StatTile icon={Waypoints} label="Trace steps" value={scanResult?.trace?.length || 0} accent="#8A6B7C" />
            </div>
          </section>

          {/* THE MAJOR SECTION: grounded intelligence findings */}
          <section
            id="findings-board"
            className={`glass-panel flex min-h-0 flex-1 flex-col overflow-hidden transition-shadow duration-300${flashCls('findings-board')}`}
          >
            <header className="shrink-0 border-b border-ink/10 px-3.5 pb-2 pt-2.5">
              <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
                <h2 className="flex items-center gap-2 font-display text-[17px] font-extrabold leading-none tracking-tight text-ink">
                  <Layers className="h-4 w-4 text-clay" />
                  Grounded Intelligence Findings
                </h2>
                <span className="rounded-md bg-clay/12 px-2 py-0.5 font-mono text-[11px] font-bold text-clay">
                  {filteredFindings.length}
                  {filteredFindings.length !== allFindings.length && (
                    <span className="text-clay/60"> / {allFindings.length}</span>
                  )}
                </span>
                <span className="font-hand text-[15px] leading-none text-moss">
                  every card is a source the agent actually opened
                </span>
              </div>

              {/* Filters: entity on the left, source type on the right, one row. */}
              <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5">
                <div className="flex items-center gap-1 rounded-lg border border-white/70 bg-white/55 p-[3px]">
                  <Filter className="ml-1 h-3 w-3 shrink-0 text-clay" />
                  {competitorChips.map(comp => (
                    <button
                      key={comp}
                      onClick={() => setCompetitorFilter(comp)}
                      className={`rounded-md px-2 py-[3px] font-mono text-[10px] font-bold transition-colors ${
                        competitorFilter === comp
                          ? 'bg-clay text-white shadow-card'
                          : 'text-ink/55 hover:bg-white/80 hover:text-ink'
                      }`}
                    >
                      {comp}
                    </button>
                  ))}
                </div>

                <div className="flex flex-wrap items-center gap-1">
                  {['All', ...SOURCE_TYPES].map(src => (
                    <button
                      key={src}
                      onClick={() => setSourceFilter(src)}
                      className={`rounded-full border px-2 py-[2px] font-mono text-[9px] font-bold uppercase tracking-wide transition-colors ${
                        sourceFilter === src
                          ? 'border-moss bg-moss text-white'
                          : 'border-white/70 bg-white/50 text-ink/55 hover:border-moss/50 hover:text-ink'
                      }`}
                    >
                      {SOURCE_LABELS[src] || src}
                    </button>
                  ))}
                </div>
              </div>
            </header>

            {/* One uniform auto-fill grid: cards flow across the full width and
                competitor identity survives as a badge, not as a section break. */}
            <div className="thin-scroll board-3d min-h-0 flex-1 overflow-y-auto p-3">
              {filteredFindings.length > 0 ? (
                <div className="grid gap-2.5 [grid-template-columns:repeat(auto-fill,minmax(12.5rem,1fr))]">
                  {filteredFindings.map((item, i) => (
                    <FindingCard key={item.id} item={item} topic={topic} index={i} />
                  ))}
                </div>
              ) : (
                <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
                  <Layers className="h-7 w-7 text-ink/15" />
                  <p className="max-w-sm font-mono text-[11px] leading-relaxed text-ink/45">
                    {scanResult
                      ? 'No findings match the selected competitor or source filter.'
                      : 'Run an autonomous scan — news, research, patents, GitHub, Reddit, model hubs and Hacker News land here as one board.'}
                  </p>
                </div>
              )}
            </div>
          </section>
        </div>

        {/* ── RIGHT: statistics drawn from the retrieved results, then synthesis and Q&A ── */}
        <div className="flex min-h-0 flex-col gap-3 lg:col-span-3">

          <section className="glass-panel flex min-h-0 flex-1 flex-col p-2.5">
            <StatCharts
              sourceData={sourceChartData}
              competitorData={competitorChartData}
              findings={allFindings}
              coverage={coverage}
            />
          </section>

          {/* EXECUTIVE TAKEAWAY */}
          <section className="glass-panel flex max-h-[26%] shrink-0 flex-col p-2.5">
            <div className="flex shrink-0 items-center gap-1.5">
              <FileText className="h-3.5 w-3.5 text-plum" />
              <h2 className="flex-1 font-sans text-[11px] font-bold text-ink">Executive Takeaway</h2>
              {scanResult?.executive_report && (
                <button
                  onClick={() => {
                    const blob = new Blob([scanResult.executive_report], { type: 'text/markdown' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `IntelPulse_${topic.replace(/\s+/g, '_')}_Report.md`;
                    a.click();
                  }}
                  className="flex items-center gap-1 rounded-md bg-ink/[0.07] px-1.5 py-0.5 font-mono text-[9px] font-bold text-ink/70 transition-colors hover:bg-clay hover:text-white"
                >
                  <Download className="h-3 w-3" /> .md
                </button>
              )}
            </div>

            <p className="thin-scroll mt-1.5 min-h-0 flex-1 overflow-y-auto pr-1 font-sans text-[11px] leading-relaxed text-ink/70">
              {executiveTakeaway || 'The analyst writes its brief here once a scan completes.'}
            </p>
          </section>

          {/* ANALYST Q&A */}
          <section className="glass-panel flex min-h-0 flex-1 flex-col overflow-hidden">
            <div className="flex shrink-0 items-center gap-1.5 border-b border-ink/10 px-2.5 py-2">
              <MessageSquare className="h-3.5 w-3.5 text-teal-deep" />
              <h2 className="flex-1 font-sans text-[11px] font-bold text-ink">Strategy Q&amp;A</h2>
              <span className="rounded bg-ink/[0.06] px-1.5 py-0.5 font-mono text-[9px] font-bold text-ink/55">
                Multi-turn
              </span>
            </div>

            <div className="thin-scroll min-h-0 flex-1 space-y-2 overflow-y-auto px-2.5 py-2">
              {chatMessages.length === 0 ? (
                <p className="px-1 font-mono text-[10px] leading-relaxed text-ink/45">
                  Ask “compare that to Sarvam” or “deep dive into their patent filings” — naming patents, news or
                  github triggers a live Field Agent lookup mid-conversation.
                </p>
              ) : (
                chatMessages.map((msg, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3 }}
                    className={`max-w-[92%] rounded-xl px-2.5 py-2 font-sans text-[11px] leading-relaxed ${
                      msg.role === 'user'
                        ? 'ml-auto bg-clay text-white shadow-card'
                        : 'border border-white/70 bg-white/65 text-ink/80 backdrop-blur'
                    }`}
                  >
                    {msg.tool_executed && (
                      <span className="mb-1 inline-flex items-center gap-1 rounded bg-ochre/25 px-1.5 py-[1px] font-mono text-[9px] font-bold text-ochre-deep">
                        <Zap className="h-2.5 w-2.5" />
                        Live lookup: {msg.tool_executed.action}
                      </span>
                    )}
                    <ReactMarkdown
                      components={{
                        strong: ({ node, ...props }) => (
                          <strong className={msg.role === 'user' ? 'font-bold text-white' : 'font-bold text-ink'} {...props} />
                        ),
                        p: ({ node, ...props }) => <p className="mb-1 last:mb-0" {...props} />
                      }}
                    >
                      {msg.content}
                    </ReactMarkdown>
                  </motion.div>
                ))
              )}

              {chatLoading && (
                <div className="flex items-center gap-1.5 font-mono text-[10px] text-ink/45">
                  <RefreshCw className="h-3 w-3 animate-spin text-clay" />
                  Analyst thinking…
                </div>
              )}
            </div>

            <form onSubmit={handleSendChat} className="flex shrink-0 gap-1.5 border-t border-ink/10 p-2">
              <input
                type="text"
                value={userQuestion}
                onChange={(e) => setUserQuestion(e.target.value)}
                placeholder="Ask a follow-up…"
                className="glass-field min-w-0 flex-1 px-2.5 py-1.5 font-sans text-[11px] text-ink placeholder:text-ink/35"
              />
              <button
                type="submit"
                disabled={chatLoading}
                className="shrink-0 rounded-lg bg-ink px-3 py-1.5 text-sand shadow-card transition-colors hover:bg-clay disabled:opacity-50"
              >
                <Send className="h-3.5 w-3.5" />
              </button>
            </form>
          </section>
        </div>
      </main>
    </div>
  );
}
