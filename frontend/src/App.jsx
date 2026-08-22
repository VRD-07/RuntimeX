import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import AgentDebugView from './debug/AgentDebugView';
import { checkHealth, runScan, sendChatMessage } from './api';
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
  BookOpen
} from 'lucide-react';

export default function App() {
  // Minimal Route Entry for Standalone Debug View (/debug/agent)
  if (typeof window !== 'undefined' && window.location.pathname.startsWith('/debug')) {
    return <AgentDebugView />;
  }

  // State
  const [topic, setTopic] = useState('Dating Apps');
  const [competitors, setCompetitors] = useState('Tinder, Bumble');
  const [maxItems, setMaxItems] = useState(5);
  const [model, setModel] = useState('claude-3-5-sonnet');
  
  const [loading, setLoading] = useState(false);
  const [health, setHealth] = useState({ status: 'checking', agentrouter_active: false });
  const [scanResult, setScanResult] = useState(null);
  const [activeTab, setActiveTab] = useState('report');
  
  // Chat state
  const [chatMessages, setChatMessages] = useState([]);
  const [userQuestion, setUserQuestion] = useState('');
  const [chatLoading, setChatLoading] = useState(false);

  // Check Backend Health on mount
  useEffect(() => {
    fetchHealth();
  }, []);

  const fetchHealth = async () => {
    const data = await checkHealth();
    setHealth(data);
  };

  const handleScan = async (e) => {
    if (e) e.preventDefault();
    setLoading(true);
    try {
      const data = await runScan(topic, competitors, maxItems, model);
      setScanResult(data);
      setActiveTab('report');
    } catch (err) {
      alert(`Scan failed: ${err.message}. Please ensure the Python FastAPI backend is running.`);
    } finally {
      setLoading(false);
    }
  };

  const handleSendChat = async (e) => {
    e.preventDefault();
    if (!userQuestion.trim()) return;

    const newMsg = { role: 'user', content: userQuestion };
    setChatMessages(prev => [...prev, newMsg]);
    setUserQuestion('');
    setChatLoading(true);

    try {
      const contextResearch = scanResult?.papers || [];
      const contextCompetitors = scanResult?.news || [];
      const res = await sendChatMessage(userQuestion, contextResearch, contextCompetitors, model);
      setChatMessages(prev => [...prev, { role: 'assistant', content: res.answer }]);
    } catch (err) {
      setChatMessages(prev => [...prev, { role: 'assistant', content: `Error: ${err.message}` }]);
    } finally {
      setChatLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Top Header */}
      <header className="border-b border-slate-800 bg-slate-900/90 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 bg-sky-500/10 border border-sky-500/30 rounded-xl text-sky-400">
              <Zap className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold bg-gradient-to-r from-sky-400 via-indigo-300 to-indigo-400 bg-clip-text text-transparent tracking-tight">
                IntelPulse Executive Intelligence
              </h1>
              <p className="text-xs text-slate-400">Autonomous Research & Competitor Tracking Platform</p>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            {/* Engine Status Badge */}
            <div className="flex items-center space-x-2 bg-slate-800/90 px-3.5 py-1.5 rounded-lg border border-slate-700 text-xs">
              <Cpu className="w-4 h-4 text-sky-400" />
              <span>
                {health.agentrouter_active ? (
                  <span className="text-emerald-400 font-semibold">AgentRouter Claude Active</span>
                ) : (
                  <span className="text-amber-400 font-medium">Fallback Engine Active</span>
                )}
              </span>
            </div>

            {/* Model Selector - Directly tied to Backend AgentRouter model selection */}
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="bg-slate-800 border border-slate-700 text-slate-200 text-xs font-medium rounded-lg px-3 py-1.5 focus:outline-none focus:border-sky-500"
              title="Select LLM Model passed to AgentRouter Backend"
            >
              <option value="claude-3-5-sonnet">Claude 3.5 Sonnet</option>
              <option value="claude-3-7-sonnet">Claude 3.7 Sonnet</option>
              <option value="claude-3-5-haiku">Claude 3.5 Haiku</option>
              <option value="gpt-4o">GPT-4o</option>
              <option value="deepseek-r1">DeepSeek R1</option>
            </select>
          </div>
        </div>
      </header>

      {/* Main Content Layout */}
      <main className="max-w-7xl mx-auto px-6 py-8 flex-1 w-full grid grid-cols-1 lg:grid-cols-12 gap-8">
        
        {/* Left Sidebar Controls (4 cols) */}
        <div className="lg:col-span-4 space-y-6">
          <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-5">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                <Search className="w-4 h-4 text-sky-400" /> Market Parameters
              </h2>
              <button 
                onClick={fetchHealth} 
                className="text-slate-400 hover:text-slate-200 transition-colors p-1"
                title="Refresh Backend Connection"
              >
                <RefreshCw className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleScan} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">
                  Industry / Domain Track
                </label>
                <input
                  type="text"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  className="w-full bg-slate-800/80 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-slate-100 focus:outline-none focus:border-sky-500 transition-colors"
                  placeholder="e.g. Dating Apps, FinTech, Quantum AI"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">
                  Target Competitors (Comma Separated)
                </label>
                <input
                  type="text"
                  value={competitors}
                  onChange={(e) => setCompetitors(e.target.value)}
                  className="w-full bg-slate-800/80 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-slate-100 focus:outline-none focus:border-sky-500 transition-colors"
                  placeholder="e.g. Tinder, Bumble, Hinge"
                  required
                />
              </div>

              <div>
                <div className="flex justify-between text-xs text-slate-400 mb-1">
                  <span>Scan Depth</span>
                  <span className="font-semibold text-slate-200">{maxItems} items per source</span>
                </div>
                <input
                  type="range"
                  min="2"
                  max="10"
                  value={maxItems}
                  onChange={(e) => setMaxItems(parseInt(e.target.value))}
                  className="w-full accent-sky-500 cursor-pointer"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white font-semibold py-3 rounded-xl shadow-lg shadow-sky-500/20 flex items-center justify-center space-x-2 transition-all disabled:opacity-50"
              >
                {loading ? (
                  <>
                    <RefreshCw className="w-5 h-5 animate-spin" />
                    <span>Scanning ArXiv & Live News...</span>
                  </>
                ) : (
                  <>
                    <Zap className="w-5 h-5" />
                    <span>Run Autonomous Intelligence Scan</span>
                  </>
                )}
              </button>
            </form>
          </div>

          {/* Quick Metric Cards */}
          {scanResult && (
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 flex items-center space-x-3">
                <div className="p-2 bg-sky-500/10 rounded-lg text-sky-400">
                  <BookOpen className="w-5 h-5" />
                </div>
                <div>
                  <p className="text-xl font-bold text-slate-100">{scanResult.papers.length}</p>
                  <p className="text-xs text-slate-400">ArXiv Papers</p>
                </div>
              </div>
              <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 flex items-center space-x-3">
                <div className="p-2 bg-indigo-500/10 rounded-lg text-indigo-400">
                  <Building2 className="w-5 h-5" />
                </div>
                <div>
                  <p className="text-xl font-bold text-slate-100">{scanResult.news.length}</p>
                  <p className="text-xs text-slate-400">Market Signals</p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right Dashboard Area (8 cols) */}
        <div className="lg:col-span-8 flex flex-col space-y-6">
          
          {/* Tabs Navigation */}
          <div className="flex border-b border-slate-800 space-x-6 text-sm font-medium">
            <button
              onClick={() => setActiveTab('report')}
              className={`pb-3 flex items-center space-x-2 border-b-2 transition-colors ${
                activeTab === 'report' ? 'border-sky-500 text-sky-400' : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <FileText className="w-4 h-4" />
              <span>Executive Brief</span>
            </button>

            <button
              onClick={() => setActiveTab('research')}
              className={`pb-3 flex items-center space-x-2 border-b-2 transition-colors ${
                activeTab === 'research' ? 'border-sky-500 text-sky-400' : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <BookOpen className="w-4 h-4" />
              <span>Research Publications ({scanResult?.papers?.length || 0})</span>
            </button>

            <button
              onClick={() => setActiveTab('news')}
              className={`pb-3 flex items-center space-x-2 border-b-2 transition-colors ${
                activeTab === 'news' ? 'border-sky-500 text-sky-400' : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Newspaper className="w-4 h-4" />
              <span>Competitor Signals ({scanResult?.news?.length || 0})</span>
            </button>

            <button
              onClick={() => setActiveTab('chat')}
              className={`pb-3 flex items-center space-x-2 border-b-2 transition-colors ${
                activeTab === 'chat' ? 'border-sky-500 text-sky-400' : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <MessageSquare className="w-4 h-4" />
              <span>Analyst Q&A</span>
            </button>
          </div>

          {/* Tab 1: Executive Report with Full Markdown Formatting & Premium Styling */}
          {activeTab === 'report' && (
            <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 space-y-4 shadow-xl">
              {scanResult ? (
                <>
                  <div className="flex justify-between items-center pb-4 border-b border-slate-800">
                    <div>
                      <h3 className="font-semibold text-slate-100 text-base">Executive Intelligence Brief</h3>
                      <p className="text-xs text-slate-400">Synthesized market analysis and research findings</p>
                    </div>
                    <button
                      onClick={() => {
                        const blob = new Blob([scanResult.executive_report], { type: 'text/markdown' });
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = `IntelPulse_${topic.replace(/\s+/g, '_')}_Report.md`;
                        a.click();
                      }}
                      className="text-xs bg-slate-800 hover:bg-slate-700 px-3.5 py-2 rounded-xl border border-slate-700 text-slate-200 flex items-center gap-2 font-medium transition-colors"
                    >
                      <Download className="w-4 h-4" /> Download Brief (.md)
                    </button>
                  </div>

                  {/* Rendered Premium HTML Typography from Markdown */}
                  <div className="report-markdown text-slate-200 text-sm space-y-4 leading-relaxed">
                    <ReactMarkdown
                      components={{
                        h1: ({node, ...props}) => <h1 className="text-xl font-bold text-slate-100 border-b border-slate-800 pb-2 mt-4 mb-3 tracking-tight" {...props} />,
                        h2: ({node, ...props}) => <h2 className="text-base font-semibold text-sky-400 mt-6 mb-2 tracking-wide uppercase" {...props} />,
                        h3: ({node, ...props}) => <h3 className="text-sm font-semibold text-indigo-300 mt-4 mb-2" {...props} />,
                        p: ({node, ...props}) => <p className="text-slate-300 mb-3 leading-relaxed" {...props} />,
                        ul: ({node, ...props}) => <ul className="list-disc list-inside space-y-1.5 text-slate-300 my-3 pl-2" {...props} />,
                        li: ({node, ...props}) => <li className="text-slate-300" {...props} />,
                        blockquote: ({node, ...props}) => <blockquote className="border-l-4 border-sky-500 bg-slate-800/40 p-4 my-4 rounded-r-xl italic text-slate-300" {...props} />,
                        hr: ({node, ...props}) => <hr className="border-slate-800 my-6" {...props} />,
                        strong: ({node, ...props}) => <strong className="font-semibold text-slate-100" {...props} />
                      }}
                    >
                      {scanResult.executive_report}
                    </ReactMarkdown>
                  </div>
                </>
              ) : (
                <div className="text-center py-20 text-slate-500 space-y-4">
                  <Zap className="w-12 h-12 mx-auto text-slate-700 animate-pulse" />
                  <div>
                    <p className="text-slate-300 font-medium text-sm">No Active Brief Generated</p>
                    <p className="text-xs text-slate-500 mt-1">Configure your domain parameters and click "Run Autonomous Scan".</p>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Tab 2: ArXiv Papers */}
          {activeTab === 'research' && (
            <div className="space-y-4">
              {scanResult?.papers?.map((paper, idx) => (
                <div key={idx} className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-colors space-y-3 shadow-sm">
                  <div className="flex justify-between items-start gap-4">
                    <h4 className="font-semibold text-slate-100 text-base leading-snug">{paper.title}</h4>
                    <span className="text-xs bg-sky-500/10 text-sky-400 border border-sky-500/20 px-2.5 py-1 rounded-lg font-medium whitespace-nowrap">
                      {paper.published}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400">Authors: {paper.authors?.join(', ')}</p>
                  <p className="text-sm text-slate-300 leading-relaxed">{paper.summary}</p>
                  <div className="pt-1">
                    <a
                      href={paper.pdf_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center space-x-1.5 text-xs text-sky-400 hover:text-sky-300 font-medium"
                    >
                      <span>Read ArXiv Paper (PDF)</span>
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Tab 3: Competitor Signals */}
          {activeTab === 'news' && (
            <div className="space-y-4">
              {scanResult?.news?.map((item, idx) => (
                <div key={idx} className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-colors space-y-3 shadow-sm">
                  <div className="flex justify-between items-start gap-4">
                    <h4 className="font-semibold text-slate-100 text-base leading-snug">{item.title}</h4>
                    <span className="text-xs bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 px-2.5 py-1 rounded-lg font-medium whitespace-nowrap">
                      {item.source_name}
                    </span>
                  </div>
                  <p className="text-sm text-slate-300 leading-relaxed">{item.snippet}</p>
                  <div className="pt-1">
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center space-x-1.5 text-xs text-indigo-400 hover:text-indigo-300 font-medium"
                    >
                      <span>View Source Article</span>
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Tab 4: Analyst Chat */}
          {activeTab === 'chat' && (
            <div className="bg-slate-900/90 border border-slate-800 rounded-2xl flex flex-col h-[520px] shadow-xl">
              <div className="p-4 border-b border-slate-800">
                <h3 className="font-semibold text-slate-200 text-sm">Interactive Strategy Q&A</h3>
                <p className="text-xs text-slate-400">Ask analytical questions over retrieved research publications and market signals.</p>
              </div>

              <div className="flex-1 p-4 overflow-y-auto space-y-3">
                {chatMessages.length === 0 ? (
                  <div className="text-center py-12 text-slate-500 space-y-2">
                    <MessageSquare className="w-8 h-8 mx-auto text-slate-700" />
                    <p className="text-xs text-slate-400">
                      Ask questions such as: "What are Tinder's key competitive vulnerabilities?" or "Summarize research matching frameworks."
                    </p>
                  </div>
                ) : (
                  chatMessages.map((msg, i) => (
                    <div
                      key={i}
                      className={`p-4 rounded-xl text-sm max-w-[85%] ${
                        msg.role === 'user'
                          ? 'ml-auto bg-sky-600 text-white font-medium'
                          : 'bg-slate-800 text-slate-200 border border-slate-700'
                      }`}
                    >
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

              <form onSubmit={handleSendChat} className="p-4 border-t border-slate-800 flex gap-3">
                <input
                  type="text"
                  value={userQuestion}
                  onChange={(e) => setUserQuestion(e.target.value)}
                  placeholder="Ask IntelPulse Strategy Advisor a question..."
                  className="flex-1 bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-slate-100 focus:outline-none focus:border-sky-500"
                />
                <button
                  type="submit"
                  disabled={chatLoading}
                  className="bg-sky-500 hover:bg-sky-400 text-white px-4 py-2.5 rounded-xl font-medium flex items-center justify-center transition-colors disabled:opacity-50"
                >
                  <Send className="w-4 h-4" />
                </button>
              </form>
            </div>
          )}

        </div>

      </main>
    </div>
  );
}
