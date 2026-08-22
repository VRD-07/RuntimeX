import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';

import AgentDebugView from './debug/AgentDebugView';
import { checkHealth, runScan, runScanStream, sendChatMessage } from './api';

import { 
  Zap, 
  Search, 
  FileText, 
  Newspaper, 
  MessageSquare, 
  ExternalLink, 
  Download, 
  Send, 
  RefreshCw,
  Cpu,
  Building2,
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
  ArrowRight
} from 'lucide-react';

const MODEL_NAMES = {
  'claude-3-5-sonnet': 'Claude 3.5 Sonnet',
  'claude-3-7-sonnet': 'Claude 3.7 Sonnet',
  'claude-3-5-haiku': 'Claude 3.5 Haiku',
  'gpt-4o': 'GPT-4o',
  'deepseek-r1': 'DeepSeek R1'
};

const CHART_COLORS = ['#C2603A', '#6E7455', '#2A2723', '#8B9467', '#D38B5D'];

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
            <span className="w-20 font-bold text-[#2A2723] truncate" title={item.name}>
              {item.name}
            </span>
            <div className="flex-1 bg-[#DCD6BE] rounded-full h-4 overflow-hidden border border-[#6E7455]/20 flex items-center">
              <div
                className="h-full rounded-full transition-all duration-700 ease-out"
                style={{ width: `${Math.max(pct, 8)}%`, backgroundColor: barColor }}
              />
            </div>
            <span className="w-8 text-right font-bold text-[#C2603A]">
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
  if (total === 0) return <div className="text-[#6E7455] text-xs">No signals</div>;

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
          <span className="text-sm font-bold text-[#2A2723]">{total}</span>
          <span className="text-[9px] text-[#6E7455]">SIGNALS</span>
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
              <span className="text-[#2A2723] font-medium">{item.name}</span>
            </div>
            <span className="font-bold text-[#6E7455]">{item.value}</span>
          </div>
        ))}
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
  const [model, setModel] = useState('claude-3-5-sonnet');
  
  const [loading, setLoading] = useState(false);
  const [health, setHealth] = useState({ status: 'checking', agentrouter_active: false });
  const [scanResult, setScanResult] = useState(null);

  // Filters state
  const [competitorFilter, setCompetitorFilter] = useState('All');
  const [sourceFilter, setSourceFilter] = useState('All');

  // Trace UI state
  const [traceExpanded, setTraceExpanded] = useState(true);
  const [staggeredStepCount, setStaggeredStepCount] = useState(0);

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

  const handleScan = async (e) => {
    if (e) e.preventDefault();
    setScanResult(null);
    setLoading(true);
    setStaggeredStepCount(0);

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
            delta: chunk.delta
          };
          dynamicTrace = [memStep, ...dynamicTrace.filter(s => s.step !== 0)];
          setScanResult({ trace: dynamicTrace });
        } else if (chunk.type === 'step_start') {
          const newStep = {
            step: chunk.step,
            agent_role: chunk.agent_role || 'Field Agent',
            thought: chunk.thought,
            action: chunk.action,
            observation: null
          };
          dynamicTrace = [...dynamicTrace.filter(s => s.step !== chunk.step), newStep].sort((a, b) => a.step - b.step);
          setScanResult({ trace: dynamicTrace });
        } else if (chunk.type === 'step_complete') {
          const updatedStep = {
            step: chunk.step,
            agent_role: chunk.agent_role || 'Field Agent',
            thought: chunk.thought,
            action: chunk.action,
            observation: chunk.observation
          };
          dynamicTrace = [...dynamicTrace.filter(s => s.step !== chunk.step), updatedStep].sort((a, b) => a.step - b.step);
          setScanResult({ trace: dynamicTrace });
        } else if (chunk.type === 'final_complete') {
          setScanResult({
            ...chunk,
            trace: dynamicTrace
          });
        }
      });
    } catch (err) {
      console.warn("Streaming error fallback:", err);
      const data = await runScan(topic, competitors, maxItems, model);
      setScanResult(data);
    } finally {
      setLoading(false);
    }
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
      const contextResearch = scanResult?.papers || [];
      const contextCompetitors = scanResult?.news || [];
      const res = await sendChatMessage(userQuestion, updatedHistory, contextResearch, contextCompetitors, model);
      
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
    const sources = ['news', 'research', 'patents', 'github', 'reddit'];
    const labels = { news: 'News', research: 'Research', patents: 'Patents', github: 'GitHub', reddit: 'Reddit' };
    return sources.map(s => {
      const count = allFindings.filter(it => it.source_type.toLowerCase() === s).length;
      return { name: labels[s], value: count };
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

    return `Strategic intelligence scan for ${topic} across ${competitors}. Key technical developments and competitor signals have been parsed across academic research, market news, USPTO patent filings, and open-source repositories. Review specific entity signals below for actionable positioning.`;
  }, [scanResult, topic, competitors]);

  const memoryRecallEvent = React.useMemo(() => {
    if (!scanResult?.trace) return null;
    return scanResult.trace.find(t => t.step_type === 'memory_recall' || t.step === 0);
  }, [scanResult]);

  return (
    <div className="min-h-screen bg-[#EAE3D2] text-[#2A2723] flex flex-col font-sans selection:bg-[#C2603A] selection:text-white relative overflow-x-hidden">
      
      {/* GLOBAL HEADER */}
      <header className="border-b border-[#6E7455]/30 bg-[#EAE3D2]/90 sticky top-0 z-50 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-3 cursor-pointer">
            <div className="p-2.5 bg-[#C2603A] text-white rounded-xl shadow-md">
              <Zap className="w-6 h-6" />
            </div>
            <div>
              <h1 className="font-serif font-bold text-xl text-[#2A2723] tracking-tight">IntelPulse ReAct Intelligence</h1>
              <p className="text-xs text-[#6E7455] font-sans">Multi-Agent Research & Memory Trace Platform</p>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            {/* Live Indicator */}
            <div className="hidden sm:flex items-center space-x-2 bg-[#DCD6BE] px-3.5 py-1.5 rounded-lg border border-[#6E7455]/40 text-xs font-mono">
              <span className="w-2.5 h-2.5 rounded-full bg-[#C2603A] animate-pulse"></span>
              <span className="text-[#2A2723] font-semibold">
                {loading ? 'ReAct Loop Active...' : 'System Live'}
              </span>
            </div>

            {/* Dynamic Model Selector Badge */}
            <div className="flex items-center space-x-2 bg-[#2A2723] text-[#EAE3D2] px-3 py-1.5 rounded-lg border border-[#6E7455]/40 text-xs font-mono">
              <Cpu className="w-4 h-4 text-[#C2603A]" />
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="bg-transparent text-[#EAE3D2] text-xs font-mono font-medium focus:outline-none cursor-pointer"
              >
                <option value="claude-3-5-sonnet" className="bg-[#2A2723] text-white">Claude 3.5 Sonnet</option>
                <option value="claude-3-7-sonnet" className="bg-[#2A2723] text-white">Claude 3.7 Sonnet</option>
                <option value="claude-3-5-haiku" className="bg-[#2A2723] text-white">Claude 3.5 Haiku</option>
                <option value="gpt-4o" className="bg-[#2A2723] text-white">GPT-4o</option>
                <option value="deepseek-r1" className="bg-[#2A2723] text-white">DeepSeek R1</option>
              </select>
            </div>
          </div>
        </div>
      </header>

      {/* DASHBOARD SINGLE SCROLL PAGE */}
      <main className="max-w-7xl mx-auto px-6 py-8 flex-1 w-full grid grid-cols-1 lg:grid-cols-12 gap-8">
        
        {/* LEFT SIDEBAR: Market Parameters (4 cols) */}
        <div className="lg:col-span-4 space-y-6">
          <div className="bg-[#DCD6BE] border border-[#6E7455]/40 rounded-2xl p-6 shadow-md space-y-5">
            <div className="flex items-center justify-between border-b border-[#6E7455]/30 pb-3">
              <h2 className="font-serif font-bold text-base text-[#2A2723] flex items-center gap-2">
                <Search className="w-4 h-4 text-[#C2603A]" />
                Market Parameters
              </h2>
              <button 
                onClick={fetchHealth} 
                className="p-1 hover:bg-[#EAE3D2] rounded-md transition-colors text-[#6E7455]"
              >
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
            </div>

            <form onSubmit={handleScan} className="space-y-4 text-xs font-sans">
              <div>
                <label className="block text-[#2A2723] font-semibold mb-1.5">
                  Industry / Domain Track
                </label>
                <input
                  type="text"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder="e.g. Regional language capabilities for AI"
                  className="w-full bg-[#EAE3D2] border border-[#6E7455]/50 rounded-xl px-3.5 py-2.5 text-[#2A2723] focus:outline-none focus:border-[#C2603A] font-medium"
                  required
                />
              </div>

              <div>
                <label className="block text-[#2A2723] font-semibold mb-1.5">
                  Target Competitors (Comma Separated)
                </label>
                <input
                  type="text"
                  value={competitors}
                  onChange={(e) => setCompetitors(e.target.value)}
                  placeholder="e.g. Sarvam, OpenAI, Google"
                  className="w-full bg-[#EAE3D2] border border-[#6E7455]/50 rounded-xl px-3.5 py-2.5 text-[#2A2723] focus:outline-none focus:border-[#C2603A] font-medium"
                  required
                />
              </div>

              <div>
                <div className="flex justify-between text-[#6E7455] mb-1.5">
                  <span className="font-semibold text-[#2A2723]">Scan Depth</span>
                  <span className="font-mono">{maxItems} items per source</span>
                </div>
                <input
                  type="range"
                  min="2"
                  max="10"
                  value={maxItems}
                  onChange={(e) => setMaxItems(parseInt(e.target.value))}
                  className="w-full accent-[#C2603A]"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-[#C2603A] hover:bg-[#a8502e] text-white font-semibold py-3 rounded-xl shadow-md transition-all flex items-center justify-center space-x-2 disabled:opacity-50"
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
          </div>

          {/* VISIBLE MEMORY TRACE PANEL (PART C) */}
          <div className="bg-[#DCD6BE] border-2 border-[#6E7455]/40 rounded-2xl p-5 shadow-md space-y-3 font-mono text-xs">
            <div className="flex items-center justify-between border-b border-[#6E7455]/30 pb-2">
              <span className="font-serif font-bold text-[#2A2723] flex items-center gap-1.5">
                <History className="w-4 h-4 text-[#C2603A]" />
                Long-Term Memory Trace
              </span>
              <span className="bg-[#2A2723] text-[#EAE3D2] text-[10px] px-2 py-0.5 rounded font-bold">
                SQLite Store
              </span>
            </div>

            {memoryRecallEvent ? (
              <div className="bg-[#EAE3D2] p-3 rounded-xl border border-[#6E7455]/30 space-y-2">
                <div className="flex items-center space-x-1.5 text-[11px] font-bold text-[#C2603A]">
                  <Clock className="w-3.5 h-3.5" />
                  <span>[Memory Recall]</span>
                </div>
                <p className="text-[#2A2723] text-xs font-medium leading-relaxed">
                  {memoryRecallEvent.content || "Loaded prior gap report for target competitor."}
                </p>
                <div className="pt-1 border-t border-[#6E7455]/20 text-[11px] text-[#6E7455] font-semibold">
                  <span className="text-[#2A2723]">Delta: </span>
                  {memoryRecallEvent.delta || "Baseline established."}
                </div>
              </div>
            ) : (
              <div className="bg-[#EAE3D2] p-3 rounded-xl border border-[#6E7455]/30 text-[#6E7455] text-center text-[11px]">
                No memory recall logged yet. Execute a scan to trigger SQLite cross-run persistence.
              </div>
            )}
          </div>

          {/* QUICK ENGINE STATS PANEL */}
          <div className="bg-[#2A2723] text-[#EAE3D2] border border-[#6E7455]/40 rounded-2xl p-5 space-y-3 font-mono text-xs shadow-md">
            <div className="flex items-center justify-between border-b border-[#6E7455]/40 pb-2">
              <span className="text-[#C2603A] font-bold">Architecture</span>
              <span>Multi-Agent + Memory</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[#6E7455]">Active Model:</span>
              <span className="text-white font-semibold">{MODEL_NAMES[model] || model}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[#6E7455]">API Key Status:</span>
              <span className={health.agentrouter_active ? "text-emerald-400 font-bold" : "text-amber-400 font-bold"}>
                {health.agentrouter_active ? "Gemini 2.5 Active" : "Fallback Engine Active"}
              </span>
            </div>
          </div>
        </div>

        {/* RIGHT DASHBOARD PAGE (8 cols) */}
        <div className="lg:col-span-8 flex flex-col space-y-8">

          {/* SECTION 1: STATS & COMPARISON CHARTS ROW */}
          <div className="bg-[#DCD6BE] border border-[#6E7455]/40 rounded-2xl p-6 shadow-md space-y-6">
            <h2 className="font-serif font-bold text-lg text-[#2A2723] flex items-center gap-2 border-b border-[#6E7455]/30 pb-3">
              <BarChart3 className="w-5 h-5 text-[#C2603A]" />
              Signal Distribution & Competitor Comparison
            </h2>

            {/* Stat Cards */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono">
              <div className="bg-[#EAE3D2] p-3.5 rounded-xl border border-[#6E7455]/30">
                <p className="text-[#6E7455] text-[11px]">Total Signals</p>
                <p className="text-2xl font-bold text-[#C2603A]">{allFindings.length}</p>
              </div>
              <div className="bg-[#EAE3D2] p-3.5 rounded-xl border border-[#6E7455]/30">
                <p className="text-[#6E7455] text-[11px]">Competitors</p>
                <p className="text-2xl font-bold text-[#2A2723]">{competitorChartData.length}</p>
              </div>
              <div className="bg-[#EAE3D2] p-3.5 rounded-xl border border-[#6E7455]/30">
                <p className="text-[#6E7455] text-[11px]">Data Sources</p>
                <p className="text-2xl font-bold text-[#6E7455]">{sourceChartData.length}</p>
              </div>
              <div className="bg-[#EAE3D2] p-3.5 rounded-xl border border-[#6E7455]/30">
                <p className="text-[#6E7455] text-[11px]">Trace Steps</p>
                <p className="text-2xl font-bold text-[#2A2723]">{scanResult?.trace?.length || 0}</p>
              </div>
            </div>

            {/* Custom SVG Charts Row */}
            {allFindings.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-12 gap-6 pt-2">
                <div className="md:col-span-7 bg-[#EAE3D2] p-4 rounded-xl border border-[#6E7455]/30 space-y-3">
                  <h4 className="font-mono text-xs font-bold text-[#2A2723]">Competitor Signal Share</h4>
                  <CompetitorBarChart data={competitorChartData} />
                </div>

                <div className="md:col-span-5 bg-[#EAE3D2] p-4 rounded-xl border border-[#6E7455]/30 space-y-3">
                  <h4 className="font-mono text-xs font-bold text-[#2A2723]">Source Breakdown</h4>
                  <SourceDonutChart data={sourceChartData} />
                </div>
              </div>
            ) : (
              <div className="bg-[#EAE3D2] p-8 rounded-xl border border-[#6E7455]/30 text-center font-mono text-xs text-[#6E7455]">
                Click "Run Autonomous Scan" to analyze competitive density and source distribution.
              </div>
            )}
          </div>

          {/* SECTION 2: EXECUTIVE SUMMARY */}
          <div className="bg-[#2A2723] text-[#EAE3D2] border border-[#6E7455]/40 rounded-2xl p-6 shadow-xl space-y-3">
            <div className="flex justify-between items-center border-b border-[#6E7455]/40 pb-3">
              <h3 className="font-serif font-bold text-base text-[#EAE3D2] flex items-center gap-2">
                <FileText className="w-5 h-5 text-[#C2603A]" />
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
                  className="text-xs bg-[#C2603A] hover:bg-[#a8502e] text-white px-3 py-1.5 rounded-lg font-mono font-medium flex items-center gap-1.5 transition-colors"
                >
                  <Download className="w-3.5 h-3.5" /> Brief (.md)
                </button>
              )}
            </div>

            <p className="text-sm text-[#DCD6BE] leading-relaxed font-sans font-medium">
              {executiveTakeaway}
            </p>
          </div>

          {/* SECTION 3: UNIFIED FILTERABLE FINDINGS GRID */}
          <div className="bg-[#DCD6BE] border border-[#6E7455]/40 rounded-2xl p-6 shadow-md space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-[#6E7455]/30 pb-4 gap-4">
              <div>
                <h3 className="font-serif font-bold text-lg text-[#2A2723] flex items-center gap-2">
                  <Layers className="w-5 h-5 text-[#C2603A]" />
                  Grounded Intelligence Findings ({filteredFindings.length})
                </h3>
                <p className="text-xs text-[#6E7455]">Filterable continuous grid of competitor signals and academic research</p>
              </div>

              {/* Filter Chips */}
              <div className="flex flex-wrap gap-2 text-xs font-mono">
                <div className="flex items-center space-x-1 bg-[#EAE3D2] p-1 rounded-lg border border-[#6E7455]/30">
                  <Filter className="w-3 h-3 text-[#C2603A] ml-1" />
                  {competitorChips.map(comp => (
                    <button
                      key={comp}
                      onClick={() => setCompetitorFilter(comp)}
                      className={`px-2.5 py-1 rounded-md transition-all font-semibold ${
                        competitorFilter === comp
                          ? 'bg-[#C2603A] text-white shadow-sm'
                          : 'text-[#6E7455] hover:text-[#2A2723]'
                      }`}
                    >
                      {comp}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Source Type Filter Sub-Bar */}
            <div className="flex flex-wrap gap-2 text-xs font-mono border-b border-[#6E7455]/20 pb-3">
              <span className="text-[#6E7455] font-semibold py-1">Source Filter:</span>
              {['All', 'news', 'research', 'patents', 'github', 'reddit'].map(src => (
                <button
                  key={src}
                  onClick={() => setSourceFilter(src)}
                  className={`px-3 py-1 rounded-full border transition-all ${
                    sourceFilter === src
                      ? 'bg-[#2A2723] text-[#EAE3D2] border-[#2A2723] font-bold'
                      : 'bg-[#EAE3D2] text-[#6E7455] border-[#6E7455]/30 hover:border-[#C2603A]'
                  }`}
                >
                  {src.toUpperCase()}
                </button>
              ))}
            </div>

            {/* Filtered Grid Cards */}
            {filteredFindings.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {filteredFindings.map((item) => {
                  const isSpecificCompetitor = item.entity && item.entity !== 'General' && item.entity !== topic;
                  return (
                    <div
                      key={item.id}
                      className={`rounded-xl p-5 flex flex-col justify-between transition-all shadow-sm ${
                        isSpecificCompetitor
                          ? 'bg-[#EAE3D2] border-2 border-[#C2603A]/70 shadow-md hover:border-[#C2603A]'
                          : 'bg-[#EAE3D2]/80 border border-[#6E7455]/30 opacity-90 hover:opacity-100'
                      }`}
                    >
                      <div className="space-y-2.5">
                        <div className="flex items-center justify-between gap-2">
                          {isSpecificCompetitor ? (
                            <span className="bg-[#C2603A] text-white font-mono font-bold px-2.5 py-0.5 rounded-md text-[11px] uppercase tracking-wider">
                              {item.entity}
                            </span>
                          ) : (
                            <span className="bg-[#6E7455]/20 text-[#6E7455] font-mono px-2 py-0.5 rounded text-[10px] font-semibold">
                              {item.entity || 'MARKET GENERAL'}
                            </span>
                          )}

                          <span className="text-[10px] font-mono text-[#6E7455] bg-[#DCD6BE] px-2 py-0.5 rounded border border-[#6E7455]/20">
                            {item.source_type.toUpperCase()}
                          </span>
                        </div>

                        <h4 className="font-serif font-bold text-sm text-[#2A2723] leading-snug">
                          {item.title}
                        </h4>

                        <p className="text-xs text-[#2A2723]/80 leading-relaxed font-sans line-clamp-3">
                          {item.snippet}
                        </p>
                      </div>

                      <div className="pt-4 mt-3 border-t border-[#6E7455]/20 flex items-center justify-between font-mono text-[11px] text-[#6E7455]">
                        <span>{item.source_name} ({item.date})</span>
                        <a
                          href={item.url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center space-x-1 text-[#C2603A] hover:underline font-semibold"
                        >
                          <span>Link</span>
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="bg-[#EAE3D2] p-12 rounded-xl border border-[#6E7455]/30 text-center font-mono text-xs text-[#6E7455]">
                {scanResult ? "No findings match the selected competitor or source filter." : "No intelligence findings available yet. Click 'Run Autonomous Scan'."}
              </div>
            )}
          </div>

          {/* SECTION 4: AGENT REASONING TRACE */}
          <div className="bg-[#2A2723] text-[#EAE3D2] border border-[#6E7455]/40 rounded-2xl shadow-xl overflow-hidden font-mono text-xs">
            <button
              onClick={() => setTraceExpanded(!traceExpanded)}
              className="w-full px-6 py-4 flex items-center justify-between border-b border-[#6E7455]/30 bg-[#2A2723] hover:bg-[#23201d] transition-colors text-left"
            >
              <div className="flex items-center space-x-3">
                <Cpu className="w-5 h-5 text-[#C2603A]" />
                <div>
                  <h3 className="font-serif font-bold text-sm text-[#EAE3D2]">
                    Multi-Agent Reasoning & Execution Trace ({scanResult?.trace?.length || 0} Steps)
                  </h3>
                  <p className="text-[11px] text-[#6E7455] font-mono">
                    Field Agent ➔ Orchestrator ➔ Analyst Agent Execution Log
                  </p>
                </div>
              </div>
              <div className="flex items-center space-x-2 text-[#C2603A]">
                <span className="text-xs font-semibold">{traceExpanded ? 'Hide Trace' : 'Expand Trace'}</span>
                {traceExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </div>
            </button>

            {traceExpanded && (
              <div className="p-6 space-y-4 bg-[#2A2723]">
                {scanResult?.trace?.length > 0 ? (
                  <div className="space-y-4">
                    {scanResult.trace.slice(0, staggeredStepCount).map((step, idx) => (
                      <div
                        key={idx}
                        className="bg-[#1F1D1A] border border-[#6E7455]/30 rounded-xl p-4 space-y-2 text-xs font-mono transition-all"
                      >
                        <div className="flex items-center justify-between border-b border-[#6E7455]/20 pb-1.5">
                          <div className="flex items-center space-x-2">
                            <span className="text-[#C2603A] font-bold">Step {step.step || idx + 1}</span>
                            {step.step_type === 'memory_recall' ? (
                              <span className="bg-amber-600 text-white px-2 py-0.5 rounded text-[10px] font-mono font-bold tracking-wider flex items-center gap-1">
                                <History className="w-3 h-3" /> MEMORY RECALL
                              </span>
                            ) : step.agent_role === 'Analyst Agent' ? (
                              <span className="bg-[#6E7455] text-white px-2 py-0.5 rounded text-[10px] font-mono font-bold tracking-wider">
                                ANALYST AGENT
                              </span>
                            ) : (
                              <span className="bg-[#C2603A] text-white px-2 py-0.5 rounded text-[10px] font-mono font-bold tracking-wider">
                                FIELD AGENT
                              </span>
                            )}
                          </div>
                          <span className="text-[10px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                            ✓ Executed
                          </span>
                        </div>
                        <div>
                          <span className="text-[#C2603A] font-bold mr-2">&gt;</span>
                          <span className="text-[#DCD6BE] font-semibold">Thought: </span>
                          <span className="text-[#EAE3D2]">{step.thought}</span>
                        </div>
                        <div>
                          <span className="text-[#C2603A] font-bold mr-2">&gt;</span>
                          <span className="text-[#D38B5D] font-semibold">Action: </span>
                          <code className="bg-[#2A2723] px-2 py-0.5 rounded text-[#D38B5D] border border-[#6E7455]/30">{step.action}</code>
                        </div>
                        {step.observation && (
                          <div className="pt-1">
                            <span className="text-[#C2603A] font-bold mr-2">&gt;</span>
                            <span className="text-sky-400 font-semibold">Observation: </span>
                            <pre className="mt-1 bg-[#2A2723] p-3 rounded-lg text-[#DCD6BE] overflow-x-auto text-[11px] whitespace-pre-wrap border border-[#6E7455]/30 max-h-48 leading-relaxed">
                              {step.observation}
                            </pre>
                          </div>
                        )}
                        {step.content && (
                          <div className="pt-1">
                            <span className="text-amber-400 font-semibold">Recall Detail: </span>
                            <span className="text-[#EAE3D2]">{step.content}</span>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-[#6E7455] text-center py-6">
                    No reasoning trace recorded yet. Run an autonomous scan above.
                  </p>
                )}
              </div>
            )}
          </div>

          {/* SECTION 5: ANALYST Q&A PANEL WITH MULTI-TURN MEMORY & LIVE TOOL BADGES */}
          <div className="bg-[#2A2723] border border-[#6E7455]/40 rounded-2xl p-6 shadow-xl space-y-4">
            <div className="border-b border-[#6E7455]/30 pb-3 flex justify-between items-center">
              <div>
                <h3 className="font-serif font-bold text-[#EAE3D2] text-base flex items-center gap-2">
                  <MessageSquare className="w-5 h-5 text-[#C2603A]" />
                  Interactive Strategy Q&A
                </h3>
                <p className="text-xs text-[#6E7455] font-sans">
                  Stateful multi-turn conversation over retrieved signals. Mentions of 'patents', 'news', or 'github' trigger real-time Field Agent lookups.
                </p>
              </div>
              <span className="bg-[#6E7455]/20 text-[#DCD6BE] text-[10px] font-mono px-2.5 py-1 rounded border border-[#6E7455]/30">
                Multi-Turn Active
              </span>
            </div>

            <div className="bg-[#1F1D1A] border border-[#6E7455]/30 rounded-xl p-4 h-[340px] overflow-y-auto space-y-3 font-sans text-xs">
              {chatMessages.length === 0 ? (
                <div className="text-center py-16 text-[#6E7455] space-y-2">
                  <MessageSquare className="w-8 h-8 mx-auto text-[#6E7455]/60" />
                  <p className="text-xs text-[#6E7455]">
                    Ask follow-up questions such as: "Now compare that to Sarvam" or "Deep dive into their patent filings."
                  </p>
                </div>
              ) : (
                chatMessages.map((msg, i) => (
                  <div
                    key={i}
                    className={`p-3.5 rounded-xl max-w-[85%] ${
                      msg.role === 'user'
                        ? 'ml-auto bg-[#C2603A] text-white font-medium shadow-sm'
                        : 'bg-[#2A2723] text-[#EAE3D2] border border-[#6E7455]/30 space-y-2'
                    }`}
                  >
                    {msg.tool_executed && (
                      <div className="inline-flex items-center space-x-1.5 bg-[#C2603A]/20 border border-[#C2603A]/50 text-[#C2603A] px-2 py-0.5 rounded text-[10px] font-mono font-bold">
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
                className="flex-1 bg-[#1F1D1A] border border-[#6E7455]/50 rounded-xl px-4 py-2.5 text-xs text-[#EAE3D2] focus:outline-none focus:border-[#C2603A]"
              />
              <button
                type="submit"
                disabled={chatLoading}
                className="bg-[#C2603A] hover:bg-[#a8502e] text-white px-5 py-2.5 rounded-xl font-semibold flex items-center justify-center transition-colors disabled:opacity-50 text-xs shadow-md"
              >
                <Send className="w-4 h-4" />
              </button>
            </form>
          </div>

        </div>
      </main>
    </div>
  );
}
