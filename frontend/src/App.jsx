import React, { useState, useEffect } from 'react';
import { checkHealth, runScan, sendChatMessage } from './api';
import { motion, AnimatePresence } from 'framer-motion';
import { BentoGrid, BentoGridItem } from './components/ui/BentoGrid';
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
  Bot,
  Globe,
  Box,
  ChevronRight,
  Database
} from 'lucide-react';

export default function App() {
  const [topic, setTopic] = useState('Agentic AI Frameworks');
  const [competitors, setCompetitors] = useState('OpenAI, Anthropic, DeepMind');
  const [maxItems, setMaxItems] = useState(5);
  const [model, setModel] = useState('claude-opus-5');
  
  const [loading, setLoading] = useState(false);
  const [health, setHealth] = useState({ status: 'checking', agentrouter_active: false });
  const [scanResult, setScanResult] = useState(null);
  const [activeTab, setActiveTab] = useState('report');
  
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

  const handleScan = async (e) => {
    if (e) e.preventDefault();
    setLoading(true);
    setScanResult(null); 
    try {
      const data = await runScan(topic, competitors, maxItems, model);
      setScanResult(data);
      setActiveTab('report');
      document.getElementById('analytics-view').scrollIntoView({ behavior: 'smooth' });
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

  const containerVariants = {
    hidden: { opacity: 0 },
    show: { opacity: 1, transition: { staggerChildren: 0.1 } }
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    show: { opacity: 1, y: 0, transition: { type: 'spring', stiffness: 300, damping: 24 } }
  };

  const tabContentVariants = {
    initial: { opacity: 0, y: 10 },
    animate: { opacity: 1, y: 0, transition: { duration: 0.3, ease: 'easeOut' } },
    exit: { opacity: 0, y: -10, transition: { duration: 0.2, ease: 'easeIn' } }
  };

  const SkeletonLoader = () => (
    <div className="space-y-8 animate-pulse">
      <div className="bg-vintage-espresso/50 backdrop-blur-3xl border border-vintage-greige/10 rounded-3xl p-8 space-y-5">
        <div className="h-6 bg-vintage-greige/10 rounded w-1/3"></div>
        <div className="space-y-3">
          <div className="h-4 bg-vintage-greige/10 rounded w-full"></div>
          <div className="h-4 bg-vintage-greige/10 rounded w-11/12"></div>
          <div className="h-4 bg-vintage-greige/10 rounded w-10/12"></div>
          <div className="h-4 bg-vintage-greige/10 rounded w-full"></div>
          <div className="h-4 bg-vintage-greige/10 rounded w-3/4"></div>
        </div>
      </div>
    </div>
  );

  // Rotating Chatbot Graphic (Vintage Palette)
  const RotatingChatbot = () => (
    <div className="relative flex items-center justify-center w-[400px] h-[400px]">
      {/* Outer Orbit 1 */}
      <motion.div 
        animate={{ rotate: 360 }}
        transition={{ duration: 25, repeat: Infinity, ease: "linear" }}
        className="absolute w-[350px] h-[350px] rounded-full border border-vintage-greige/10"
      >
        <div className="absolute top-12 left-[15%] w-3 h-3 bg-vintage-rosewood rounded-full shadow-[0_0_15px_3px_rgba(125,64,71,0.6)]"></div>
      </motion.div>

      {/* Inner Orbit 2 */}
      <motion.div 
        animate={{ rotate: -360 }}
        transition={{ duration: 18, repeat: Infinity, ease: "linear" }}
        className="absolute w-[240px] h-[240px] rounded-full border border-vintage-greige/5"
      >
        <div className="absolute top-8 right-10 w-2.5 h-2.5 bg-vintage-cream rounded-full shadow-[0_0_20px_4px_rgba(241,236,230,0.8)]"></div>
      </motion.div>

      {/* Core Dark Circle */}
      <div className="absolute w-36 h-36 bg-vintage-base border border-vintage-rosewood/30 rounded-full flex items-center justify-center shadow-[0_0_50px_rgba(125,64,71,0.2)] z-10">
        <motion.div
          animate={{ rotate: [0, 5, -5, 0] }}
          transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
        >
          <Bot className="w-14 h-14 text-vintage-cream" />
        </motion.div>
      </div>
      
      {/* Subtle background glow */}
      <div className="absolute w-[300px] h-[300px] bg-vintage-rosewood/10 rounded-full blur-[80px] pointer-events-none"></div>
    </div>
  );

  return (
    <div className="min-h-screen bg-vintage-base text-vintage-cream font-sans selection:bg-vintage-rosewood/30 selection:text-vintage-cream relative">
      {/* Subtle Noise Texture Overlay */}
      <div className="fixed inset-0 z-0 opacity-[0.03] pointer-events-none mix-blend-overlay" style={{ backgroundImage: 'url("data:image/svg+xml,%3Csvg viewBox=%220 0 200 200%22 xmlns=%22http://www.w3.org/2000/svg%22%3E%3Cfilter id=%22noiseFilter%22%3E%3CfeTurbulence type=%22fractalNoise%22 baseFrequency=%220.65%22 numOctaves=%223%22 stitchTiles=%22stitch%22/%3E%3C/filter%3E%3Crect width=%22100%25%22 height=%22100%25%22 filter=%22url(%23noiseFilter)%22/%3E%3C/svg%3E")' }}></div>

      {/* Top Navbar */}
      <header className="relative z-50 border-b border-vintage-greige/10 bg-vintage-base/80 backdrop-blur-md sticky top-0">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-8">
            <motion.div 
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center space-x-2 group cursor-pointer"
              onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
            >
              <div className="w-0 h-0 border-l-[10px] border-l-transparent border-r-[10px] border-r-transparent border-b-[18px] border-b-vintage-rosewood transition-transform group-hover:scale-110"></div>
              <h1 className="text-xl font-bold tracking-tight text-vintage-cream ml-2 group-hover:text-white transition-colors">IntelPulse</h1>
            </motion.div>
          </div>

          <motion.div 
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex items-center space-x-4"
          >
            <div className="hidden md:flex items-center space-x-2 bg-vintage-greige/5 px-4 py-2 rounded-md border border-vintage-greige/10 text-xs font-medium tracking-wide">
              <Cpu className="w-4 h-4 text-vintage-greige" />
              <span>
                {health.agentrouter_active ? (
                  <span className="text-vintage-cream font-semibold">AgentRouter</span>
                ) : (
                  <span className="text-vintage-cream/70">Fallback</span>
                )}
              </span>
            </div>
          </motion.div>
        </div>
      </header>

      {/* 1. Immersive Agentic Infrastructure Hero */}
      <section className="relative z-10 w-full min-h-[85vh] flex items-center justify-center overflow-hidden pt-20 pb-16">
        
        <div className="max-w-7xl mx-auto px-6 w-full relative z-30 -mt-12 md:-mt-24">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-16 items-center">
              
              {/* Left Col (Text & CTAs) */}
              <div className="flex flex-col items-start z-30 order-2 md:order-1">
                 <motion.h1 
                    initial={{ opacity: 0, filter: 'blur(10px)' }}
                    animate={{ opacity: 1, filter: 'blur(0px)' }}
                    transition={{ duration: 1 }}
                    className="flex flex-col text-5xl md:text-[5rem] tracking-tighter text-vintage-cream leading-[1.05]"
                 >
                   <span className="font-montserrat font-extrabold uppercase tracking-wide text-[0.8em] text-vintage-cream drop-shadow-sm">Autonomous</span>
                   <span className="font-playfair italic font-normal text-vintage-cream mt-2 ml-1 md:ml-2 drop-shadow-md">Infrastructure</span>
                 </motion.h1>
                 
                 <motion.div 
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.4, duration: 0.8 }}
                    className="flex items-center space-x-4 mt-10"
                 >
                   <button 
                     onClick={() => document.getElementById('analytics-view').scrollIntoView({ behavior: 'smooth' })} 
                     className="bg-vintage-rosewood text-vintage-cream font-montserrat font-bold uppercase tracking-wider text-xs px-8 py-4 rounded-full hover:scale-105 hover:shadow-[0_0_30px_rgba(125,64,71,0.6)] transition-all duration-300 shadow-[0_0_20px_rgba(125,64,71,0.4)]"
                   >
                     Research now
                   </button>
                 </motion.div>
              </div>

              {/* Right Col (Rotating Chatbot) */}
              <motion.div 
                 initial={{ opacity: 0 }}
                 animate={{ opacity: 1 }}
                 transition={{ duration: 1.5 }}
                 className="relative flex justify-center md:justify-end z-20 order-1 md:order-2"
              >
                 <RotatingChatbot />
              </motion.div>

          </div>
        </div>
      </section>

      {/* 2. Analytics View (The IntelPulse Dashboard) */}
      <section id="analytics-view" className="relative z-20 max-w-7xl mx-auto px-6 py-24 w-full border-t border-vintage-greige/10 mt-10">
        
        <div className="mb-16 text-center">
           <h2 className="text-3xl md:text-4xl font-bold text-vintage-cream tracking-tight">Intelligence Console</h2>
           <p className="text-vintage-greige mt-4 max-w-xl mx-auto text-lg">Define parameters to execute an autonomous deep scan across your specified domain.</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          
          {/* Left Column: Form & Stats */}
          <div className="lg:col-span-4 space-y-6">
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5 }}
              className="bg-vintage-espresso border border-vintage-greige/20 rounded-2xl p-6 shadow-2xl relative overflow-hidden"
            >
              
              <div className="flex items-center justify-between mb-8">
                <h2 className="text-sm font-semibold text-vintage-cream flex items-center gap-2">
                  <Search className="w-4 h-4 text-vintage-greige" /> Target Parameters
                </h2>
                <motion.button 
                  whileHover={{ rotate: 180 }}
                  transition={{ duration: 0.3 }}
                  onClick={fetchHealth} 
                  className="text-vintage-greige hover:text-vintage-cream transition-colors p-1"
                >
                  <RefreshCw className="w-4 h-4" />
                </motion.button>
              </div>

              <form onSubmit={handleScan} className="space-y-6">
                <div className="space-y-2">
                  <label className="block text-xs font-semibold text-vintage-greige">
                    Research Topic / Domain
                  </label>
                  <input
                    type="text"
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    className="w-full bg-vintage-base border border-vintage-greige/20 rounded-lg px-4 py-3 text-sm text-vintage-cream font-medium focus:outline-none focus:border-vintage-rosewood focus:ring-1 focus:ring-vintage-rosewood transition-all shadow-inner"
                    required
                  />
                </div>

                <div className="space-y-2">
                  <label className="block text-xs font-semibold text-vintage-greige">
                    Competitors / Keywords
                  </label>
                  <input
                    type="text"
                    value={competitors}
                    onChange={(e) => setCompetitors(e.target.value)}
                    className="w-full bg-vintage-base border border-vintage-greige/20 rounded-lg px-4 py-3 text-sm text-vintage-cream font-medium focus:outline-none focus:border-vintage-rosewood focus:ring-1 focus:ring-vintage-rosewood transition-all shadow-inner"
                    required
                  />
                </div>

                <div className="space-y-2 pt-2">
                  <div className="flex justify-between text-xs text-vintage-greige font-semibold">
                    <span>Scan Depth</span>
                    <span className="text-vintage-cream">{maxItems} items / source</span>
                  </div>
                  <input
                    type="range"
                    min="2"
                    max="10"
                    value={maxItems}
                    onChange={(e) => setMaxItems(parseInt(e.target.value))}
                    className="w-full accent-vintage-rosewood cursor-pointer"
                  />
                </div>
                
                <div className="space-y-2 pt-2">
                   <label className="block text-xs font-semibold text-vintage-greige">Model Selection</label>
                   <select
                     value={model}
                     onChange={(e) => setModel(e.target.value)}
                     className="w-full bg-vintage-base border border-vintage-greige/20 text-vintage-cream text-sm font-medium rounded-lg px-4 py-3 focus:outline-none focus:border-vintage-rosewood focus:ring-1 focus:ring-vintage-rosewood transition-colors cursor-pointer appearance-none"
                   >
                     <option value="claude-opus-4-8">Claude Opus 4.8</option>
                     <option value="claude-opus-5">Claude Opus 5</option>
                     <option value="gpt-5.6-sol">GPT 5.6 Sol</option>
                   </select>
                </div>

                <div className="pt-4">
                  <button
                    className="w-full bg-vintage-rosewood text-vintage-cream flex items-center justify-center space-x-2 px-4 py-3 rounded-lg font-semibold text-sm hover:opacity-90 transition-opacity disabled:opacity-50 shadow-[0_0_10px_rgba(125,64,71,0.2)]"
                    type="submit"
                    disabled={loading}
                  >
                    {loading ? (
                      <>
                        <RefreshCw className="w-4 h-4 animate-spin" />
                        <span>Aggregating Data...</span>
                      </>
                    ) : (
                      <>
                        <Zap className="w-4 h-4" />
                        <span>Execute Autonomous Scan</span>
                      </>
                    )}
                  </button>
                </div>
              </form>
            </motion.div>

            <AnimatePresence>
              {scanResult && !loading && (
                <motion.div 
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="grid grid-cols-2 gap-4"
                >
                  <div className="bg-vintage-espresso border border-vintage-greige/20 rounded-2xl p-6 text-center shadow-lg">
                    <p className="text-4xl font-bold text-vintage-cream tracking-tight">{scanResult.papers.length}</p>
                    <p className="text-[11px] text-vintage-greige mt-1 font-semibold uppercase tracking-wider">ArXiv Papers</p>
                  </div>
                  <div className="bg-vintage-espresso border border-vintage-greige/20 rounded-2xl p-6 text-center shadow-lg">
                    <p className="text-4xl font-bold text-vintage-cream tracking-tight">{scanResult.news.length}</p>
                    <p className="text-[11px] text-vintage-greige mt-1 font-semibold uppercase tracking-wider">Signals</p>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Right Column: Dynamic Tabs & Data Vis */}
          <motion.div 
            initial={{ opacity: 0, y: 40 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="lg:col-span-8 flex flex-col space-y-6"
          >
            <div className="flex border-b border-vintage-greige/10 space-x-8 text-sm font-semibold overflow-x-auto overflow-y-hidden scrollbar-hide pb-[1px]">
              {[
                { id: 'report', label: 'Executive Report' },
                { id: 'research', label: `Papers (${scanResult?.papers?.length || 0})` },
                { id: 'news', label: `News (${scanResult?.news?.length || 0})` },
                { id: 'chat', label: 'Analyst Chat' },
              ].map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`pb-4 px-1 relative transition-colors whitespace-nowrap ${
                    activeTab === tab.id ? 'text-vintage-cream' : 'text-vintage-greige hover:text-vintage-cream'
                  }`}
                >
                  <span>{tab.label}</span>
                  {activeTab === tab.id && (
                    <motion.div
                      layoutId="activeTabIndicator"
                      className="absolute bottom-0 left-0 right-0 h-0.5 bg-vintage-rosewood"
                      initial={false}
                      transition={{ type: "spring", stiffness: 500, damping: 30 }}
                    />
                  )}
                </button>
              ))}
            </div>

            <div className="relative min-h-[600px]">
              {loading ? (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="w-full">
                  <div className="bg-vintage-espresso border border-vintage-greige/20 rounded-2xl h-[400px] flex items-center justify-center">
                     <RefreshCw className="w-8 h-8 text-vintage-greige animate-spin" />
                  </div>
                </motion.div>
              ) : !scanResult ? (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col items-center justify-center py-40 text-vintage-greige space-y-6 bg-vintage-espresso/30 border border-vintage-greige/10 rounded-[2rem] border-dashed">
                  <Box className="w-16 h-16 opacity-30" />
                  <p className="text-sm font-semibold tracking-wide text-vintage-greige">Awaiting scan execution...</p>
                </motion.div>
              ) : (
                <AnimatePresence mode="wait">
                  {activeTab === 'report' && (
                    <motion.div 
                      key="report"
                      variants={tabContentVariants}
                      initial="initial" animate="animate" exit="exit"
                      className="bg-vintage-espresso border border-vintage-greige/20 rounded-[2rem] p-10 space-y-8 shadow-xl"
                    >
                      <div className="flex justify-between items-center pb-6 border-b border-vintage-greige/10">
                        <h3 className="font-semibold text-vintage-cream text-lg tracking-tight">Synthesized Digest</h3>
                        <motion.button
                          whileHover={{ scale: 1.02 }}
                          whileTap={{ scale: 0.98 }}
                          onClick={() => {
                            const blob = new Blob([scanResult.executive_report], { type: 'text/markdown' });
                            const url = URL.createObjectURL(blob);
                            const a = document.createElement('a');
                            a.href = url;
                            a.download = 'intelpulse_report.md';
                            a.click();
                          }}
                          className="text-xs bg-vintage-rosewood text-vintage-cream px-4 py-2 rounded-md font-semibold flex items-center gap-2 transition-opacity hover:opacity-90 shadow-md"
                        >
                          <Download className="w-3.5 h-3.5" /> Export MD
                        </motion.button>
                      </div>
                      <div className="prose prose-invert max-w-none text-vintage-cream/90 text-sm whitespace-pre-line leading-relaxed">
                        {scanResult.executive_report}
                      </div>
                    </motion.div>
                  )}

                  {activeTab === 'research' && (
                    <motion.div key="research" variants={containerVariants} initial="hidden" animate="show" exit={{ opacity: 0 }} className="space-y-4">
                      {scanResult?.papers?.map((paper, idx) => (
                        <motion.div variants={itemVariants} key={idx} className="bg-vintage-espresso border border-vintage-greige/20 rounded-xl p-6 hover:border-vintage-rosewood/50 transition-all duration-300 space-y-3 shadow-lg group cursor-default">
                          <div className="flex justify-between items-start gap-4">
                            <h4 className="font-semibold text-vintage-cream text-base leading-snug">{paper.title}</h4>
                            <span className="text-[10px] uppercase font-bold bg-vintage-greige/10 text-vintage-cream px-2 py-1 rounded whitespace-nowrap">
                              {paper.published}
                            </span>
                          </div>
                          <p className="text-xs text-vintage-greige font-medium uppercase tracking-wide">Authors: {paper.authors?.join(', ')}</p>
                          <p className="text-sm text-vintage-cream/80 leading-relaxed line-clamp-2">{paper.summary}</p>
                          <div className="pt-3">
                            <a href={paper.pdf_url} target="_blank" rel="noreferrer" className="inline-flex items-center space-x-1.5 text-xs font-semibold text-vintage-rosewood hover:text-vintage-rosewood/80 transition-colors">
                              <span>Read Full Document</span>
                              <ExternalLink className="w-3 h-3" />
                            </a>
                          </div>
                        </motion.div>
                      ))}
                    </motion.div>
                  )}

                  {activeTab === 'news' && (
                    <motion.div key="news" variants={containerVariants} initial="hidden" animate="show" exit={{ opacity: 0 }} className="space-y-4">
                      {scanResult?.news?.map((item, idx) => (
                        <motion.div variants={itemVariants} key={idx} className="bg-vintage-espresso border border-vintage-greige/20 rounded-xl p-6 hover:border-vintage-rosewood/50 transition-all duration-300 space-y-3 shadow-lg group cursor-default">
                          <div className="flex justify-between items-start gap-4">
                            <h4 className="font-semibold text-vintage-cream text-base leading-snug">{item.title}</h4>
                            <span className="text-[10px] uppercase font-bold bg-vintage-greige/10 text-vintage-cream px-2 py-1 rounded whitespace-nowrap">
                              {item.source_name}
                            </span>
                          </div>
                          <p className="text-sm text-vintage-cream/80 leading-relaxed">{item.snippet}</p>
                          <div className="pt-3">
                            <a href={item.url} target="_blank" rel="noreferrer" className="inline-flex items-center space-x-1.5 text-xs font-semibold text-vintage-rosewood hover:text-vintage-rosewood/80 transition-colors">
                              <span>Source Verification</span>
                              <ExternalLink className="w-3 h-3" />
                            </a>
                          </div>
                        </motion.div>
                      ))}
                    </motion.div>
                  )}

                  {activeTab === 'chat' && (
                    <motion.div key="chat" variants={tabContentVariants} initial="initial" animate="animate" exit="exit" className="bg-vintage-espresso border border-vintage-greige/20 rounded-2xl flex flex-col h-[600px] shadow-xl overflow-hidden">
                      <div className="p-5 border-b border-vintage-greige/10 bg-vintage-espresso">
                        <h3 className="font-semibold text-vintage-cream text-sm flex items-center gap-2">
                          <MessageSquare className="w-4 h-4 text-vintage-greige" /> AI Analyst
                        </h3>
                      </div>

                      <div className="flex-1 p-6 overflow-y-auto space-y-6">
                        <AnimatePresence initial={false}>
                          {chatMessages.length === 0 ? (
                            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col items-center justify-center h-full text-center space-y-3 opacity-80">
                               <Bot className="w-8 h-8 text-vintage-greige" />
                               <p className="text-sm font-medium text-vintage-greige">
                                 Query the synthesized data repository.
                               </p>
                            </motion.div>
                          ) : (
                            chatMessages.map((msg, i) => (
                              <motion.div key={i} initial={{ opacity: 0, y: 10, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} className={`p-4 rounded-xl text-sm max-w-[85%] font-medium flex gap-4 leading-relaxed shadow-sm ${msg.role === 'user' ? 'ml-auto bg-vintage-rosewood text-vintage-cream rounded-br-sm' : 'bg-vintage-base border border-vintage-greige/10 text-vintage-cream rounded-bl-sm'}`}>
                                {msg.role === 'assistant' && (
                                  <div className="w-6 h-6 rounded-md bg-vintage-greige/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                                    <Bot className="w-3 h-3 text-vintage-cream" />
                                  </div>
                                )}
                                <p className="whitespace-pre-line">{msg.content}</p>
                              </motion.div>
                            ))
                          )}
                          {chatLoading && (
                            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="p-4 rounded-xl text-sm max-w-[85%] bg-vintage-base border border-vintage-greige/10 text-vintage-greige rounded-bl-sm flex gap-2 items-center shadow-md">
                              <span className="animate-bounce">.</span><span className="animate-bounce delay-75">.</span><span className="animate-bounce delay-150">.</span>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>

                      <form onSubmit={handleSendChat} className="p-4 border-t border-vintage-greige/10 bg-vintage-espresso flex gap-3">
                        <input type="text" value={userQuestion} onChange={(e) => setUserQuestion(e.target.value)} placeholder="Ask a question..." className="flex-1 bg-vintage-base border border-vintage-greige/20 rounded-lg px-4 py-3 text-sm text-vintage-cream focus:outline-none focus:border-vintage-rosewood transition-all" />
                        <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} type="submit" disabled={chatLoading} className="bg-vintage-rosewood text-vintage-cream hover:opacity-90 px-5 rounded-lg disabled:opacity-50 flex items-center justify-center transition-opacity shadow-md">
                          <Send className="w-4 h-4" />
                        </motion.button>
                      </form>
                    </motion.div>
                  )}
                </AnimatePresence>
              )}
            </div>
          </motion.div>
        </div>
      </section>

      {/* 3. Core Architecture (Vintage Style) */}
      <section className="relative z-10 bg-vintage-base pt-24 pb-32 border-t border-vintage-greige/10">
        <div className="max-w-7xl mx-auto px-6">
          <div className="mb-20 text-center md:text-left">
             <h2 className="text-3xl font-bold text-vintage-cream tracking-tight">Core Architecture</h2>
             <p className="text-vintage-greige mt-2 text-lg">A highly polished suite of tools designed to instantly aggregate and synthesize unstructured data.</p>
          </div>

          <BentoGrid>
            <BentoGridItem
              title="Advanced NLU Engine"
              description="Deep intent recognition routing complex queries to specialized local models."
              icon={<Zap className="w-5 h-5 text-vintage-cream" />}
              className="md:col-span-1 bg-vintage-espresso border-vintage-greige/10 hover:border-vintage-rosewood/50 transition-all duration-300"
              header={<div className="w-full h-40 rounded-xl overflow-hidden bg-vintage-base"><img src="/nlu_engine.jpg" alt="NLU Engine" className="w-full h-full object-cover object-center transition-transform duration-500 hover:scale-105" /></div>}
            />
            <BentoGridItem
              title="Real-Time Data Synthesis"
              description="Aggregate ArXiv papers and competitor signals into structured Markdown reports instantly."
              icon={<Globe className="w-5 h-5 text-vintage-cream" />}
              className="md:col-span-1 bg-vintage-espresso border-vintage-greige/10 hover:border-vintage-rosewood/50 transition-all duration-300"
              header={<div className="w-full h-40 rounded-xl overflow-hidden bg-vintage-base"><img src="/data_synthesis.jpg" alt="Data Synthesis" className="w-full h-full object-cover object-center transition-transform duration-500 hover:scale-105" /></div>}
            />
            <BentoGridItem
              title="Context-Aware Chat"
              description="Converse directly with your synthesized data using the interactive AI Analyst."
              icon={<Box className="w-5 h-5 text-vintage-cream" />}
              className="md:col-span-1 bg-vintage-espresso border-vintage-greige/10 hover:border-vintage-rosewood/50 transition-all duration-300"
              header={<div className="w-full h-40 rounded-xl overflow-hidden bg-vintage-base"><img src="/context_chat.jpg" alt="Context Chat" className="w-full h-full object-cover object-center transition-transform duration-500 hover:scale-105" /></div>}
            />
          </BentoGrid>
        </div>
      </section>

    </div>
  );
}
