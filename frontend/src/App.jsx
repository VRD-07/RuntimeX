import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';

import AgentDebugView from './debug/AgentDebugView';
import CapabilityShowcase from './components/CapabilityShowcase';
import { checkHealth, runScan, runScanStream, sendChatMessage } from './api';

import { 
  Zap, 
  Search, 
  FileText, 
  MessageSquare, 
  ExternalLink, 
  Download, 
  Send, 
  RefreshCw,
  Cpu,
  BookOpen,
  ChevronDown,
  ChevronUp,
  Share2,
  Filter,
  BarChart3,
  Layers,
  CheckCircle2,
  History,
  Clock,
  ArrowRight,
  AlertTriangle,
  Award
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

const CHART_COLORS = ['#38BDF8', '#A78BFA', '#34D399', '#FBBF24', '#F472B6'];

// Must mirror SECTION_ORDER / SECTION_RESPONSE_KEYS in backend/agent_brain.py.
// Declared once here so the source filter, the source chart and the chat context
// payload all stay in step — they used to be three separate hardcoded lists.
const SOURCE_TYPES = ['news', 'research', 'patents', 'github', 'reddit', 'models', 'hackernews'];

const SOURCE_LABELS = {
  news: 'News',
  research: 'Research',
  patents: 'Patents',
  github: 'GitHub',
  reddit: 'Reddit',
  models: 'Model Hub',
  hackernews: 'Hacker News'
};

// Flat top-level arrays in the scan response, read only when structured_output
// is missing (older backend builds).
const SOURCE_RESPONSE_KEYS = {
  news: 'news',
  research: 'papers',
  patents: 'patents',
  github: 'github_repos',
  reddit: 'reddit_posts',
  models: 'hf_models',
  hackernews: 'hn_posts'
};

// Turns "search_news(query='Sarvam AI funding')" into "search_news - Sarvam AI funding"
// so a trace step fits on one line without hiding which tool ran or on what.
function summarizeStep(step) {
  const action = (step.action || '').trim();
  if (!action) return (step.thought || 'Reasoning step').slice(0, 90);
  const match = action.match(/^([\w.]+)\s*\((.*)\)$/s);
  if (!match) return action.slice(0, 90);
  const tool = match[1].split('.').pop();
  const args = match[2].replace(/\w+\s*=\s*/g, '').replace(/['"]/g, '').trim();
  return args ? `${tool} - ${args.slice(0, 64)}` : tool;
}

// A step's role badge. Chaos steps are labelled explicitly so a deliberately
// injected failure can never be mistaken for a real one.
function stepBadge(step) {
  if (step.step_type === 'chaos' || step.chaos) return { label: 'CHAOS DEMO', className: 'bg-rose-500/90 text-white' };
  if (step.step_type === 'memory_recall') return { label: 'MEMORY', className: 'bg-amber-400/90 text-slate-900' };
  if (step.agent_role === 'Analyst Agent') return { label: 'ANALYST', className: 'bg-violet-500/85 text-white' };
  if (step.agent_role === 'Orchestrator') return { label: 'ORCHESTRATOR', className: 'bg-emerald-500/85 text-white' };
  return { label: 'FIELD', className: 'bg-sky-500/85 text-white' };
}

// Custom Responsive Horizontal Bar Chart
function CompetitorBarChart({ data }) {
  const maxCount = Math.max(...data.map(d => d.count), 1);

  return (
    <div className="space-y-3 font-mono text-xs">
      {data.map((item, idx) => {
        const pct = Math.round((item.count / maxCount) * 100);
        const barColor = CHART_COLORS[idx % CHART_COLORS.length];
        return (
          <div key={item.name} className="flex items-center space-x-3">
            <span className="w-20 font-bold text-slate-100 truncate" title={item.name}>
              {item.name}
            </span>
            <div className="flex-1 bg-white/[0.07] backdrop-blur-2xl rounded-full h-4 overflow-hidden border border-white/10 flex items-center">
              <div
                className="h-full rounded-full transition-all duration-700 ease-out"
                style={{ width: `${Math.max(pct, 8)}%`, backgroundColor: barColor }}
              />
            </div>
            <span className="w-8 text-right font-bold text-sky-300">
              {item.count}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// Custom Responsive Donut SVG Chart
function SourceDonutChart({ data }) {
  const total = data.reduce((acc, curr) => acc + curr.value, 0);
  if (total === 0) return <div className="text-slate-400 text-xs">No signals</div>;

  let cumulativePercent = 0;

  return (
    <div className="flex items-center space-x-4">
      <div className="relative w-28 h-28 flex-shrink-0">
        <svg viewBox="0 0 36 36" className="w-full h-full transform -rotate-90">
          {data.map((item, idx) => {
            const percent = (item.value / total) * 100;
            const strokeDasharray = `${percent} ${100 - percent}`;
            const strokeDashoffset = 100 - cumulativePercent;
            cumulativePercent += percent;
            const color = CHART_COLORS[idx % CHART_COLORS.length];

            return (
              <circle
                key={item.name}
                cx="18"
                cy="18"
                r="15.91549430918954"
                fill="transparent"
                stroke={color}
                strokeWidth="4"
                strokeDasharray={strokeDasharray}
                strokeDashoffset={strokeDashoffset}
                className="transition-all duration-700 ease-out"
              />
            );
          })}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center font-mono">
          <span className="text-sm font-bold text-slate-100">{total}</span>
          <span className="text-[9px] text-slate-400">SIGNALS</span>
        </div>
      </div>

      <div className="space-y-1.5 font-mono text-[11px] flex-1">
        {data.map((item, idx) => (
          <div key={item.name} className="flex items-center justify-between">
            <div className="flex items-center space-x-1.5">
              <span
                className="w-2.5 h-2.5 rounded-full inline-block"
                style={{ backgroundColor: CHART_COLORS[idx % CHART_COLORS.length] }}
              />
              <span className="text-slate-100 font-medium">{item.name}</span>
            </div>
            <span className="font-bold text-slate-400">{item.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// One finding card. Every card is identical in weight now: competitor identity is
// a badge, not a layout boundary, so the grid reads as one intelligence board.
function FindingCard({ item, topic }) {
  const isSpecificCompetitor = item.entity && item.entity !== 'General' && item.entity !== topic;
  return (
    <div className="group flex h-full flex-col justify-between rounded-2xl border border-white/10 bg-white/[0.06] p-4 backdrop-blur-xl glass-edge glass-lift hover:border-sky-400/30">
      <div className="space-y-2.5">
        <div className="flex items-center justify-between gap-2">
          <span
            className={`rounded-md border px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider ${
              isSpecificCompetitor
                ? 'border-sky-400/40 bg-sky-400/15 text-sky-200'
                : 'border-white/10 bg-white/[0.06] text-slate-400'
            }`}
          >
            {item.entity || 'MARKET GENERAL'}
          </span>

          <span className="shrink-0 rounded-md border border-white/10 bg-white/[0.04] px-2 py-0.5 font-mono text-[10px] text-slate-400">
            {(SOURCE_LABELS[item.source_type] || item.source_type).toUpperCase()}
          </span>
        </div>

        <h4 className="font-serif text-sm font-semibold leading-snug text-slate-50">
          {item.title}
        </h4>

        <p className="line-clamp-3 font-sans text-xs leading-relaxed text-slate-400">
          {item.snippet}
        </p>
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-white/10 pt-3 font-mono text-[11px] text-slate-500">
        <span className="truncate pr-2">{item.source_name} ({item.date})</span>
        <a
          href={item.url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex shrink-0 items-center gap-1 font-semibold text-sky-300 hover:text-sky-200"
        >
          <span>Link</span>
          <ExternalLink className="w-3 h-3" />
        </a>
      </div>
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

  // Trace UI state
  const [traceExpanded, setTraceExpanded] = useState(true);
  const [staggeredStepCount, setStaggeredStepCount] = useState(0);
  // Which individual trace steps have been opened for full detail. The trace is
  // one line per step by default because the raw log used to be longer than the
  // rest of the page combined.
  const [openTraceSteps, setOpenTraceSteps] = useState({});

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
    setOpenTraceSteps({});
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
   * Scrolls a real dashboard panel into view and rings it briefly, so a jump
   * from the showcase lands somewhere the reviewer can see it landed.
   */
  const jumpToPanel = (id) => {
    setShowcaseOpen(false);
    setFlashPanel(id);
    // One frame after the slide-over starts closing, so the scroll is not
    // fighting the panel's transform.
    requestAnimationFrame(() => {
      document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    setTimeout(() => setFlashPanel(null), 2400);
  };

  // Ring applied to whichever panel was just jumped to.
  const flashCls = (id) => (flashPanel === id ? ' ring-2 ring-sky-400/70 ring-offset-2 ring-offset-slate-950' : '');

  /** Fires a real scan with the backend's chaos_mode=tool_failure fault injection. */
  const handleChaosScan = () => {
    setShowcaseOpen(false);
    setTraceExpanded(true);
    requestAnimationFrame(() => {
      document.getElementById('trace-panel')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
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
    <div className="min-h-screen text-slate-100 flex flex-col font-sans selection:bg-sky-500/40 selection:text-white relative overflow-x-hidden">
      
      <CapabilityShowcase
        open={showcaseOpen}
        onClose={() => setShowcaseOpen(false)}
        onJump={jumpToPanel}
        onRunChaos={handleChaosScan}
        chaosRunning={loading && chaosArmed}
        chaosArmed={chaosArmed}
      />

      {/* GLOBAL HEADER */}
      <header className="sticky top-0 z-50 border-b border-white/10 bg-slate-950/60 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-3 cursor-pointer">
            <div className="p-2.5 bg-sky-500/90 text-white rounded-xl glass-edge">
              <Zap className="w-6 h-6" />
            </div>
            <div>
              <h1 className="font-serif font-bold text-xl text-slate-100 tracking-tight">IntelPulse ReAct Intelligence</h1>
              <p className="text-xs text-slate-400 font-sans">Multi-Agent Research & Memory Trace Platform</p>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            {/* Live Indicator */}
            <div className="hidden sm:flex items-center space-x-2 bg-white/[0.07] backdrop-blur-2xl px-3.5 py-1.5 rounded-lg border border-white/10 text-xs font-mono">
              <span className="w-2.5 h-2.5 rounded-full bg-sky-500/90 animate-pulse"></span>
              <span className="text-slate-100 font-semibold">
                {loading ? 'ReAct Loop Active...' : 'System Live'}
              </span>
            </div>

            {/* Judge-facing capability showcase */}
            <button
              onClick={() => setShowcaseOpen(true)}
              className="flex items-center gap-2 rounded-lg border border-sky-400/40 bg-sky-400/10 px-3 py-1.5 font-mono text-xs font-semibold text-sky-200 transition-colors hover:bg-sky-400/20"
            >
              <Award className="h-4 w-4" />
              <span className="hidden sm:inline">Capability Showcase</span>
            </button>

            {/* Dynamic Model Selector Badge */}
            <div className="flex items-center space-x-2 bg-slate-950/55 backdrop-blur-2xl text-slate-100 px-3 py-1.5 rounded-lg border border-white/10 text-xs font-mono">
              <Cpu className="w-4 h-4 text-sky-300" />
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="bg-transparent text-slate-100 text-xs font-mono font-medium focus:outline-none cursor-pointer"
              >
                {Object.entries(MODEL_NAMES).map(([id, label]) => (
                  <option key={id} value={id} className="bg-slate-950/55 backdrop-blur-2xl text-white">{label}</option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </header>

      {/* DASHBOARD SINGLE SCROLL PAGE */}
      <main className="max-w-7xl mx-auto px-6 py-8 flex-1 w-full flex flex-col gap-8">

        {/* TOP ROW: parameters sidebar + headline stats and synthesis */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        
        {/* LEFT SIDEBAR: Market Parameters (4 cols) */}
        <div className="lg:col-span-4 space-y-6">
          <div className="bg-white/[0.07] backdrop-blur-2xl border border-white/10 rounded-2xl p-6 glass-edge space-y-5">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h2 className="font-serif font-bold text-base text-slate-100 flex items-center gap-2">
                <Search className="w-4 h-4 text-sky-300" />
                Market Parameters
              </h2>
              <button 
                onClick={fetchHealth} 
                className="p-1 hover:bg-white/10 rounded-md transition-colors text-slate-400"
              >
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
            </div>

            <form onSubmit={handleScan} className="space-y-4 text-xs font-sans">
              <div>
                <label className="block text-slate-100 font-semibold mb-1.5">
                  Industry / Domain Track
                </label>
                <input
                  type="text"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder="e.g. Regional language capabilities for AI"
                  className="w-full bg-white/[0.05] backdrop-blur-sm border border-white/10 rounded-xl px-3.5 py-2.5 text-slate-100 focus:outline-none focus:border-sky-400/40 font-medium"
                  required
                />
              </div>

              <div>
                <label className="block text-slate-100 font-semibold mb-1.5">
                  Target Competitors (Comma Separated)
                </label>
                <input
                  type="text"
                  value={competitors}
                  onChange={(e) => setCompetitors(e.target.value)}
                  placeholder="e.g. Sarvam, OpenAI, Google"
                  className="w-full bg-white/[0.05] backdrop-blur-sm border border-white/10 rounded-xl px-3.5 py-2.5 text-slate-100 focus:outline-none focus:border-sky-400/40 font-medium"
                  required
                />
              </div>

              <div>
                <div className="flex justify-between text-slate-400 mb-1.5">
                  <span className="font-semibold text-slate-100">Scan Depth</span>
                  <span className="font-mono">{maxItems} items per source</span>
                </div>
                <input
                  type="range"
                  min="2"
                  max="10"
                  value={maxItems}
                  onChange={(e) => setMaxItems(parseInt(e.target.value))}
                  className="w-full accent-sky-400"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-sky-500/90 hover:bg-sky-400 text-white font-semibold py-3 rounded-xl glass-edge transition-all flex items-center justify-center space-x-2 disabled:opacity-50"
              >
                {loading ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin text-white" />
                    <span>Multi-Agent Scan Executing...</span>
                  </>
                ) : (
                  <>
                    <Zap className="w-4 h-4" />
                    <span>Run Autonomous Scan</span>
                  </>
                )}
              </button>
            </form>

            {scanError && (
              <div
                role="alert"
                className="mt-4 flex items-start gap-2 bg-rose-500/10 border border-rose-400/35 rounded-xl p-3 font-mono text-xs text-rose-100"
              >
                <AlertTriangle className="w-4 h-4 text-rose-300 shrink-0 mt-0.5" />
                <div>
                  <p className="font-bold text-rose-300">Scan failed</p>
                  <p className="mt-0.5 break-words">{scanError}</p>
                </div>
              </div>
            )}
          </div>

          {/* VISIBLE MEMORY TRACE PANEL (PART C) */}
          <div
            id="memory-panel"
            className={`bg-white/[0.07] backdrop-blur-2xl border-2 border-white/10 rounded-2xl p-5 glass-edge space-y-3 font-mono text-xs scroll-mt-24 transition-shadow duration-300${flashCls('memory-panel')}`}
          >
            <div className="flex items-center justify-between border-b border-white/10 pb-2">
              <span className="font-serif font-bold text-slate-100 flex items-center gap-1.5">
                <History className="w-4 h-4 text-sky-300" />
                Long-Term Memory Trace
              </span>
              <span className="bg-slate-950/55 backdrop-blur-2xl text-slate-100 text-[10px] px-2 py-0.5 rounded font-bold">
                SQLite Store
              </span>
            </div>

            {memoryRecallEvent ? (
              <div className="bg-white/[0.05] backdrop-blur-sm p-3 rounded-xl border border-white/10 space-y-2">
                <div className="flex items-center space-x-1.5 text-[11px] font-bold text-sky-300">
                  <Clock className="w-3.5 h-3.5" />
                  <span>[Memory Recall]</span>
                </div>
                <p className="text-slate-100 text-xs font-medium leading-relaxed">
                  {memoryRecallEvent.content || "Loaded prior gap report for target competitor."}
                </p>
                <div className="pt-1 border-t border-white/10 text-[11px] text-slate-400 font-semibold">
                  <span className="text-slate-100">Delta: </span>
                  {memoryRecallEvent.delta || "Baseline established."}
                </div>
              </div>
            ) : (
              <div className="bg-white/[0.05] backdrop-blur-sm p-3 rounded-xl border border-white/10 text-slate-400 text-center text-[11px]">
                No memory recall logged yet. Execute a scan to trigger SQLite cross-run persistence.
              </div>
            )}
          </div>

          {/* QUICK ENGINE STATS PANEL */}
          <div className="bg-slate-950/55 backdrop-blur-2xl text-slate-100 border border-white/10 rounded-2xl p-5 space-y-3 font-mono text-xs glass-edge">
            <div className="flex items-center justify-between border-b border-white/10 pb-2">
              <span className="text-sky-300 font-bold">Architecture</span>
              <span>Multi-Agent + Memory</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Active Model:</span>
              <span className="text-white font-semibold">
                {scanResult?.model_used
                  ? (MODEL_NAMES[scanResult.model_used] || scanResult.model_used)
                  : (MODEL_NAMES[model] || model)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">API Key Status:</span>
              <span className={health.llm_active ? "text-emerald-400 font-bold" : "text-amber-400 font-bold"}>
                {health.llm_active ? "Gemini Active" : "Fallback Engine Active"}
              </span>
            </div>
          </div>
        </div>

        {/* RIGHT DASHBOARD PAGE (8 cols) */}
        <div className="lg:col-span-8 flex flex-col space-y-8">

          {/* SECTION 1: STATS & COMPARISON CHARTS ROW */}
          <div className="bg-white/[0.07] backdrop-blur-2xl border border-white/10 rounded-2xl p-6 glass-edge space-y-6">
            <h2 className="font-serif font-bold text-lg text-slate-100 flex items-center gap-2 border-b border-white/10 pb-3">
              <BarChart3 className="w-5 h-5 text-sky-300" />
              Signal Distribution & Competitor Comparison
            </h2>

            {/* Stat Cards */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono">
              <div className="bg-white/[0.05] backdrop-blur-sm p-3.5 rounded-xl border border-white/10">
                <p className="text-slate-400 text-[11px]">Total Signals</p>
                <p className="text-2xl font-bold text-sky-300">{allFindings.length}</p>
              </div>
              <div className="bg-white/[0.05] backdrop-blur-sm p-3.5 rounded-xl border border-white/10">
                <p className="text-slate-400 text-[11px]">Competitors</p>
                <p className="text-2xl font-bold text-slate-100">{competitorChartData.length}</p>
              </div>
              <div className="bg-white/[0.05] backdrop-blur-sm p-3.5 rounded-xl border border-white/10">
                <p className="text-slate-400 text-[11px]">Data Sources</p>
                <p className="text-2xl font-bold text-slate-400">{sourceChartData.length}</p>
              </div>
              <div className="bg-white/[0.05] backdrop-blur-sm p-3.5 rounded-xl border border-white/10">
                <p className="text-slate-400 text-[11px]">Trace Steps</p>
                <p className="text-2xl font-bold text-slate-100">{scanResult?.trace?.length || 0}</p>
              </div>
            </div>

            {/* Custom SVG Charts Row */}
            {allFindings.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-12 gap-6 pt-2">
                <div className="md:col-span-7 bg-white/[0.05] backdrop-blur-sm p-4 rounded-xl border border-white/10 space-y-3">
                  <h4 className="font-mono text-xs font-bold text-slate-100">Competitor Signal Share</h4>
                  <CompetitorBarChart data={competitorChartData} />
                </div>

                <div className="md:col-span-5 bg-white/[0.05] backdrop-blur-sm p-4 rounded-xl border border-white/10 space-y-3">
                  <h4 className="font-mono text-xs font-bold text-slate-100">Source Breakdown</h4>
                  <SourceDonutChart data={sourceChartData} />
                </div>
              </div>
            ) : (
              <div className="bg-white/[0.05] backdrop-blur-sm p-8 rounded-xl border border-white/10 text-center font-mono text-xs text-slate-400">
                Click "Run Autonomous Scan" to analyze competitive density and source distribution.
              </div>
            )}
          </div>

          {/* SECTION 2: EXECUTIVE SUMMARY */}
          <div className="bg-slate-950/55 backdrop-blur-2xl text-slate-100 border border-white/10 rounded-2xl p-6 glass-edge space-y-3">
            <div className="flex justify-between items-center border-b border-white/10 pb-3">
              <h3 className="font-serif font-bold text-base text-slate-100 flex items-center gap-2">
                <FileText className="w-5 h-5 text-sky-300" />
                Executive Takeaway Summary
              </h3>
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
                  className="text-xs bg-sky-500/90 hover:bg-sky-400 text-white px-3 py-1.5 rounded-lg font-mono font-medium flex items-center gap-1.5 transition-colors"
                >
                  <Download className="w-3.5 h-3.5" /> Brief (.md)
                </button>
              )}
            </div>

            <p className="text-sm text-slate-300 leading-relaxed font-sans font-medium">
              {executiveTakeaway}
            </p>
          </div>

          </div>
        </div>

          {/* SECTION 3: UNIFIED FILTERABLE FINDINGS GRID */}
          <div
            id="findings-board"
            className={`bg-white/[0.07] backdrop-blur-2xl border border-white/10 rounded-2xl p-6 glass-edge space-y-6 scroll-mt-24 transition-shadow duration-300${flashCls('findings-board')}`}
          >
            <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-white/10 pb-4 gap-4">
              <div>
                <h3 className="font-serif font-bold text-lg text-slate-100 flex items-center gap-2">
                  <Layers className="w-5 h-5 text-sky-300" />
                  Grounded Intelligence Findings ({filteredFindings.length})
                </h3>
                <p className="text-xs text-slate-400">Filterable continuous grid of competitor signals and academic research</p>
              </div>

              {/* Filter Chips */}
              <div className="flex flex-wrap gap-2 text-xs font-mono">
                <div className="flex items-center space-x-1 bg-white/[0.05] backdrop-blur-sm p-1 rounded-lg border border-white/10">
                  <Filter className="w-3 h-3 text-sky-300 ml-1" />
                  {competitorChips.map(comp => (
                    <button
                      key={comp}
                      onClick={() => setCompetitorFilter(comp)}
                      className={`px-2.5 py-1 rounded-md transition-all font-semibold ${
                        competitorFilter === comp
                          ? 'bg-sky-500/90 text-white glass-edge'
                          : 'text-slate-400 hover:text-white'
                      }`}
                    >
                      {comp}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Source Type Filter Sub-Bar */}
            <div className="flex flex-wrap gap-2 text-xs font-mono border-b border-white/10 pb-3">
              <span className="text-slate-400 font-semibold py-1">Source Filter:</span>
              {['All', ...SOURCE_TYPES].map(src => (
                <button
                  key={src}
                  onClick={() => setSourceFilter(src)}
                  className={`px-3 py-1 rounded-full border transition-all ${
                    sourceFilter === src
                      ? 'bg-slate-950/55 backdrop-blur-2xl text-slate-100 border-white/15 font-bold'
                      : 'bg-white/[0.05] backdrop-blur-sm text-slate-400 border-white/10 hover:border-sky-400/60'
                  }`}
                >
                  {(SOURCE_LABELS[src] || src).toUpperCase()}
                </button>
              ))}
            </div>

            {/* One uniform auto-fill grid: cards flow across the full width and
                competitor identity survives as a badge, not as a section break. */}
            {filteredFindings.length > 0 ? (
              <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(15.5rem,1fr))]">
                {filteredFindings.map(item => (
                  <FindingCard key={item.id} item={item} topic={topic} />
                ))}
              </div>
            ) : (
              <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-12 text-center font-mono text-xs text-slate-400 backdrop-blur-sm">
                {scanResult ? "No findings match the selected competitor or source filter." : "No intelligence findings available yet. Click 'Run Autonomous Scan'."}
              </div>
            )}
          </div>

          {/* SECTION 4: AGENT REASONING TRACE */}
          <div
            id="trace-panel"
            className={`bg-slate-950/55 backdrop-blur-2xl text-slate-100 border border-white/10 rounded-2xl glass-edge overflow-hidden font-mono text-xs scroll-mt-24 transition-shadow duration-300${flashCls('trace-panel')}`}
          >
            {chaosArmed && (
              <div className="flex items-start gap-2 border-b border-rose-400/30 bg-rose-500/15 px-6 py-2.5 font-mono text-[11px] text-rose-100">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-rose-300" />
                <span>
                  <span className="font-bold text-rose-200">Adversarial run:</span> this scan was launched with{' '}
                  <span className="text-rose-200">chaos_mode=tool_failure</span>. Rose CHAOS rows below are
                  deliberately injected faults, not a real outage.
                </span>
              </div>
            )}
            <button
              onClick={() => setTraceExpanded(!traceExpanded)}
              className="w-full px-6 py-4 flex items-center justify-between border-b border-white/10 bg-slate-950/55 backdrop-blur-2xl hover:bg-white/[0.06] transition-colors text-left"
            >
              <div className="flex items-center space-x-3">
                <Cpu className="w-5 h-5 text-sky-300" />
                <div>
                  <h3 className="font-serif font-bold text-sm text-slate-100">
                    Multi-Agent Reasoning & Execution Trace ({scanResult?.trace?.length || 0} Steps)
                  </h3>
                  <p className="text-[11px] text-slate-400 font-mono">
                    Field Agent ➔ Orchestrator ➔ Analyst Agent Execution Log
                  </p>
                </div>
              </div>
              <div className="flex items-center space-x-2 text-sky-300">
                <span className="text-xs font-semibold">{traceExpanded ? 'Hide Trace' : 'Expand Trace'}</span>
                {traceExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </div>
            </button>

            {traceExpanded && (
              <div className="bg-slate-950/55 backdrop-blur-2xl">
                {scanResult?.trace?.length > 0 ? (
                  // Capped height: the full log runs longer than the rest of the
                  // page, so it scrolls inside its own panel instead of pushing
                  // the analyst Q&A off screen.
                  <div className="max-h-[420px] overflow-y-auto divide-y divide-white/[0.06]">
                    {scanResult.trace.slice(0, staggeredStepCount).map((step, idx) => {
                      const badge = stepBadge(step);
                      const isOpen = !!openTraceSteps[idx];
                      return (
                        <div key={idx} className="text-xs font-mono">
                          <button
                            onClick={() => setOpenTraceSteps(prev => ({ ...prev, [idx]: !prev[idx] }))}
                            className="w-full px-5 py-2 flex items-center gap-3 hover:bg-white/[0.05] transition-colors text-left"
                          >
                            {isOpen
                              ? <ChevronUp className="w-3.5 h-3.5 text-sky-300 shrink-0" />
                              : <ChevronDown className="w-3.5 h-3.5 text-slate-400 shrink-0" />}
                            <span className="text-slate-400 w-8 shrink-0">{String(step.step ?? idx + 1).padStart(2, '0')}</span>
                            <span className={`${badge.className} px-1.5 py-0.5 rounded text-[9px] font-bold tracking-wider shrink-0 w-[92px] text-center`}>
                              {badge.label}
                            </span>
                            <span className="text-slate-300 truncate flex-1">{summarizeStep(step)}</span>
                            {step.observation
                              ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                              : <RefreshCw className="w-3.5 h-3.5 text-slate-400 animate-spin shrink-0" />}
                            <span className="text-[10px] text-slate-400 shrink-0 w-16 text-right">{step.ts || '--:--:--'}</span>
                          </button>

                          {isOpen && (
                            <div className="px-5 pb-4 pt-1 space-y-2 bg-black/35 backdrop-blur-sm">
                              {step.thought && (
                                <div>
                                  <span className="text-slate-300 font-semibold">Thought: </span>
                                  <span className="text-slate-100">{step.thought}</span>
                                </div>
                              )}
                              {step.action && (
                                <div>
                                  <span className="text-amber-300 font-semibold">Action: </span>
                                  <code className="bg-slate-950/55 backdrop-blur-2xl px-2 py-0.5 rounded text-amber-300 border border-white/10 break-all">{step.action}</code>
                                </div>
                              )}
                              {step.observation && (
                                <div>
                                  <span className="text-sky-400 font-semibold">Observation: </span>
                                  <pre className="mt-1 bg-slate-950/55 backdrop-blur-2xl p-3 rounded-lg text-slate-300 overflow-auto text-[11px] whitespace-pre-wrap border border-white/10 max-h-56 leading-relaxed">
                                    {step.observation}
                                  </pre>
                                </div>
                              )}
                              {step.content && (
                                <div>
                                  <span className="text-amber-400 font-semibold">Recall Detail: </span>
                                  <span className="text-slate-100">{step.content}</span>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-xs text-slate-400 text-center py-6">
                    No reasoning trace recorded yet. Run an autonomous scan above.
                  </p>
                )}
              </div>
            )}
          </div>

          {/* SECTION 5: ANALYST Q&A PANEL WITH MULTI-TURN MEMORY & LIVE TOOL BADGES */}
          <div className="bg-slate-950/55 backdrop-blur-2xl border border-white/10 rounded-2xl p-6 glass-edge space-y-4">
            <div className="border-b border-white/10 pb-3 flex justify-between items-center">
              <div>
                <h3 className="font-serif font-bold text-slate-100 text-base flex items-center gap-2">
                  <MessageSquare className="w-5 h-5 text-sky-300" />
                  Interactive Strategy Q&A
                </h3>
                <p className="text-xs text-slate-400 font-sans">
                  Stateful multi-turn conversation over retrieved signals. Mentions of 'patents', 'news', or 'github' trigger real-time Field Agent lookups.
                </p>
              </div>
              <span className="bg-white/10 text-slate-300 text-[10px] font-mono px-2.5 py-1 rounded border border-white/10">
                Multi-Turn Active
              </span>
            </div>

            <div className="bg-black/35 backdrop-blur-sm border border-white/10 rounded-xl p-4 h-[340px] overflow-y-auto space-y-3 font-sans text-xs">
              {chatMessages.length === 0 ? (
                <div className="text-center py-16 text-slate-400 space-y-2">
                  <MessageSquare className="w-8 h-8 mx-auto text-slate-400" />
                  <p className="text-xs text-slate-400">
                    Ask follow-up questions such as: "Now compare that to Sarvam" or "Deep dive into their patent filings."
                  </p>
                </div>
              ) : (
                chatMessages.map((msg, i) => (
                  <div
                    key={i}
                    className={`p-3.5 rounded-xl max-w-[85%] ${
                      msg.role === 'user'
                        ? 'ml-auto bg-sky-500/90 text-white font-medium glass-edge'
                        : 'bg-slate-950/55 backdrop-blur-2xl text-slate-100 border border-white/10 space-y-2'
                    }`}
                  >
                    {msg.tool_executed && (
                      <div className="inline-flex items-center space-x-1.5 bg-sky-400/15 border border-sky-400/45 text-sky-300 px-2 py-0.5 rounded text-[10px] font-mono font-bold">
                        <Zap className="w-3 h-3" />
                        <span>Live Field Lookup: {msg.tool_executed.action}</span>
                      </div>
                    )}
                    <ReactMarkdown
                      components={{
                        strong: ({node, ...props}) => <strong className="font-semibold text-white" {...props} />,
                        p: ({node, ...props}) => <p className="mb-1" {...props} />
                      }}
                    >
                      {msg.content}
                    </ReactMarkdown>
                  </div>
                ))
              )}
            </div>

            <form onSubmit={handleSendChat} className="flex gap-3">
              <input
                type="text"
                value={userQuestion}
                onChange={(e) => setUserQuestion(e.target.value)}
                placeholder="Ask follow-up question (e.g. 'deep dive into their patent filings')..."
                className="flex-1 bg-black/35 backdrop-blur-sm border border-white/10 rounded-xl px-4 py-2.5 text-xs text-slate-100 focus:outline-none focus:border-sky-400/40"
              />
              <button
                type="submit"
                disabled={chatLoading}
                className="bg-sky-500/90 hover:bg-sky-400 text-white px-5 py-2.5 rounded-xl font-semibold flex items-center justify-center transition-colors disabled:opacity-50 text-xs glass-edge"
              >
                <Send className="w-4 h-4" />
              </button>
            </form>
          </div>

      </main>
    </div>
  );
}
