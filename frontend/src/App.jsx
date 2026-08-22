import React, { useState, useEffect } from 'react';
import { checkHealth, runScan, sendChatMessage } from './api';
import { 
  Zap, 
  Search, 
  FileText, 
  Newspaper, 
  MessageSquare, 
  ShieldCheck, 
  ExternalLink, 
  Download, 
  Send, 
  RefreshCw,
  Cpu
} from 'lucide-react';

export default function App() {
  // State
  const [topic, setTopic] = useState('Agentic AI Frameworks');
  const [competitors, setCompetitors] = useState('OpenAI, Anthropic, DeepMind');
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
      alert(`Scan failed: ${err.message}. Make sure FastAPI backend is running!`);
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
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-sky-500/10 border border-sky-500/30 rounded-xl text-sky-400">
              <Zap className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold bg-gradient-to-r from-sky-400 to-indigo-400 bg-clip-text text-transparent">
                IntelPulse AI Agent
              </h1>
              <p className="text-xs text-slate-400">Autonomous Research & Competitor Intelligence Platform</p>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            {/* Engine Status Badge */}
            <div className="flex items-center space-x-2 bg-slate-800/80 px-3 py-1.5 rounded-lg border border-slate-700 text-xs">
              <Cpu className="w-4 h-4 text-sky-400" />
              <span>
                {health.agentrouter_active ? (
                  <span className="text-emerald-400 font-medium">🟢 AgentRouter Claude Active</span>
                ) : (
                  <span className="text-amber-400 font-medium">🟡 Fallback Engine</span>
                )}
              </span>
            </div>

            {/* Model Selector */}
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-1.5 focus:outline-none focus:border-sky-500"
            >
              <option value="claude-3-5-sonnet">Claude 3.5 Sonnet</option>
              <option value="claude-3-haiku">Claude 3 Haiku</option>
              <option value="claude-3-opus">Claude 3 Opus</option>
            </select>
          </div>
        </div>
      </header>

      {/* Main Content Layout */}
      <main className="max-w-7xl mx-auto px-6 py-8 flex-1 w-full grid grid-cols-1 lg:grid-cols-12 gap-8">
        
        {/* Left Sidebar / Form Controls (4 cols) */}
        <div className="lg:col-span-4 space-y-6">
          <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-5">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-slate-200 flex items-center gap-2">
                <Search className="w-4 h-4 text-sky-400" /> Tracking Targets
              </h2>
              <button 
                onClick={fetchHealth} 
                className="text-slate-400 hover:text-slate-200 transition-colors p-1"
                title="Refresh Backend Status"
              >
                <RefreshCw className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleScan} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">
                  Research Topic / Domain
                </label>
                <input
                  type="text"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-slate-100 focus:outline-none focus:border-sky-500 transition-colors"
                  placeholder="e.g. Agentic AI Frameworks"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">
                  Competitors / Keywords
                </label>
                <input
                  type="text"
                  value={competitors}
                  onChange={(e) => setCompetitors(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-slate-100 focus:outline-none focus:border-sky-500 transition-colors"
                  placeholder="e.g. OpenAI, Anthropic, Google"
                  required
                />
              </div>

              <div>
                <div className="flex justify-between text-xs text-slate-400 mb-1">
                  <span>Scan Depth</span>
                  <span className="font-semibold text-slate-200">{maxItems} items / source</span>
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
                className="w-full bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white font-medium py-3 rounded-xl shadow-lg shadow-sky-500/20 flex items-center justify-center space-x-2 transition-all disabled:opacity-50"
              >
                {loading ? (
                  <>
                    <RefreshCw className="w-5 h-5 animate-spin" />
                    <span>Scanning ArXiv & News...</span>
                  </>
                ) : (
                  <>
                    <Zap className="w-5 h-5" />
                    <span>Run Autonomous Scan</span>
                  </>
                )}
              </button>
            </form>
          </div>

          {/* Quick Metrics */}
          {scanResult && (
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 text-center">
                <p className="text-2xl font-bold text-sky-400">{scanResult.papers.length}</p>
                <p className="text-xs text-slate-400 mt-1">ArXiv Papers</p>
              </div>
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 text-center">
                <p className="text-2xl font-bold text-indigo-400">{scanResult.news.length}</p>
                <p className="text-xs text-slate-400 mt-1">Competitor News</p>
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
              <span>Executive Report</span>
            </button>

            <button
              onClick={() => setActiveTab('research')}
              className={`pb-3 flex items-center space-x-2 border-b-2 transition-colors ${
                activeTab === 'research' ? 'border-sky-500 text-sky-400' : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <FileText className="w-4 h-4" />
              <span>Research Papers ({scanResult?.papers?.length || 0})</span>
            </button>

            <button
              onClick={() => setActiveTab('news')}
              className={`pb-3 flex items-center space-x-2 border-b-2 transition-colors ${
                activeTab === 'news' ? 'border-sky-500 text-sky-400' : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Newspaper className="w-4 h-4" />
              <span>Competitor News ({scanResult?.news?.length || 0})</span>
            </button>

            <button
              onClick={() => setActiveTab('chat')}
              className={`pb-3 flex items-center space-x-2 border-b-2 transition-colors ${
                activeTab === 'chat' ? 'border-sky-500 text-sky-400' : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <MessageSquare className="w-4 h-4" />
              <span>Analyst Chat</span>
            </button>
          </div>

          {/* Tab 1: Executive Report */}
          {activeTab === 'report' && (
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">
              {scanResult ? (
                <>
                  <div className="flex justify-between items-center pb-3 border-b border-slate-800">
                    <h3 className="font-semibold text-slate-200">Synthesized Executive Intelligence Digest</h3>
                    <button
                      onClick={() => {
                        const blob = new Blob([scanResult.executive_report], { type: 'text/markdown' });
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = 'executive_report.md';
                        a.click();
                      }}
                      className="text-xs bg-slate-800 hover:bg-slate-700 px-3 py-1.5 rounded-lg border border-slate-700 text-slate-300 flex items-center gap-1.5"
                    >
                      <Download className="w-3.5 h-3.5" /> Download MD
                    </button>
                  </div>
                  <div className="prose prose-invert max-w-none text-slate-300 text-sm whitespace-pre-line leading-relaxed">
                    {scanResult.executive_report}
                  </div>
                </>
              ) : (
                <div className="text-center py-16 text-slate-500 space-y-3">
                  <Zap className="w-12 h-12 mx-auto text-slate-700 animate-pulse" />
                  <p>Run an autonomous scan to generate your executive report.</p>
                </div>
              )}
            </div>
          )}

          {/* Tab 2: ArXiv Papers */}
          {activeTab === 'research' && (
            <div className="space-y-4">
              {scanResult?.papers?.map((paper, idx) => (
                <div key={idx} className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-colors space-y-2">
                  <div className="flex justify-between items-start">
                    <h4 className="font-semibold text-slate-100 text-base">{paper.title}</h4>
                    <span className="text-xs bg-sky-500/10 text-sky-400 border border-sky-500/20 px-2 py-0.5 rounded">
                      {paper.published}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400">Authors: {paper.authors?.join(', ')}</p>
                  <p className="text-sm text-slate-300 line-clamp-3">{paper.summary}</p>
                  <div className="pt-2">
                    <a
                      href={paper.pdf_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center space-x-1 text-xs text-sky-400 hover:underline"
                    >
                      <span>Read Full ArXiv Paper</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Tab 3: Competitor News */}
          {activeTab === 'news' && (
            <div className="space-y-4">
              {scanResult?.news?.map((item, idx) => (
                <div key={idx} className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-colors space-y-2">
                  <div className="flex justify-between items-start">
                    <h4 className="font-semibold text-slate-100 text-base">{item.title}</h4>
                    <span className="text-xs bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 px-2 py-0.5 rounded">
                      {item.source_name}
                    </span>
                  </div>
                  <p className="text-sm text-slate-300">{item.snippet}</p>
                  <div className="pt-2">
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center space-x-1 text-xs text-indigo-400 hover:underline"
                    >
                      <span>Visit Source Article</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Tab 4: Analyst Chat */}
          {activeTab === 'chat' && (
            <div className="bg-slate-900 border border-slate-800 rounded-2xl flex flex-col h-[500px]">
              <div className="p-4 border-b border-slate-800">
                <h3 className="font-semibold text-slate-200 text-sm">Interactive AI Analyst Chat</h3>
                <p className="text-xs text-slate-400">Ask strategic questions about scanned papers & market signals.</p>
              </div>

              <div className="flex-1 p-4 overflow-y-auto space-y-3">
                {chatMessages.length === 0 ? (
                  <p className="text-xs text-slate-500 text-center py-8">
                    Ask questions like: "What are the key technical breakthroughs from the papers?" or "Summarize competitor threats."
                  </p>
                ) : (
                  chatMessages.map((msg, i) => (
                    <div
                      key={i}
                      className={`p-3.5 rounded-xl text-sm max-w-[85%] ${
                        msg.role === 'user'
                          ? 'ml-auto bg-sky-600 text-white'
                          : 'bg-slate-800 text-slate-200 border border-slate-700'
                      }`}
                    >
                      <p className="whitespace-pre-line">{msg.content}</p>
                    </div>
                  ))
                )}
              </div>

              <form onSubmit={handleSendChat} className="p-4 border-t border-slate-800 flex gap-2">
                <input
                  type="text"
                  value={userQuestion}
                  onChange={(e) => setUserQuestion(e.target.value)}
                  placeholder="Ask IntelPulse Analyst..."
                  className="flex-1 bg-slate-800 border border-slate-700 rounded-xl px-4 py-2 text-sm text-slate-100 focus:outline-none focus:border-sky-500"
                />
                <button
                  type="submit"
                  disabled={chatLoading}
                  className="bg-sky-500 hover:bg-sky-400 text-white p-2.5 rounded-xl disabled:opacity-50"
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
