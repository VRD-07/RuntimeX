import os
import streamlit as st
import pandas as pd
import json
from dotenv import load_dotenv

from tools.research_tool import fetch_arxiv_papers
from tools.competitor_tool import fetch_competitor_news
from agent_brain import AgentRouterBrain

# Load environment variables
load_dotenv()

st.set_page_config(
    page_title="IntelPulse - Research & Competitor Tracking Agent",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.3rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        padding: 1rem;
        border-radius: 8px;
        text-align: center;
    }
    .card-title {
        font-weight: 600;
        font-size: 1.1rem;
        color: #0F172A;
    }
    .status-badge {
        background-color: #DEF7EC;
        color: #03543F;
        font-size: 0.85rem;
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# App Title & Header
st.markdown('<div class="main-header">⚡ IntelPulse AI Agent</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Autonomous Research & Competitor Tracking Platform • Powered by AgentRouter Claude</div>', unsafe_allow_html=True)

# Initialize Session State
if "scan_results" not in st.session_state:
    st.session_state.scan_results = None
if "executive_report" not in st.session_state:
    st.session_state.executive_report = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Load environment variables securely
env_api_key = os.getenv("AGENTROUTER_API_KEY", "")
env_base_url = os.getenv("AGENTROUTER_BASE_URL", "https://agentrouter.ai/v1")
env_model = os.getenv("AGENTROUTER_MODEL", "claude-3-5-sonnet")

# Sidebar Controls
st.sidebar.header("🎯 Autonomous Tracking Controls")

# Status Badge in Sidebar
if env_api_key:
    st.sidebar.success("🟢 AgentRouter Claude: Active")
else:
    st.sidebar.info("🟡 Engine Mode: Fallback / Mock")

model_choice = st.sidebar.selectbox(
    "Claude Model", 
    ["claude-3-5-sonnet", "claude-3-haiku", "claude-3-opus"],
    index=0
)

st.sidebar.divider()
track_topic = st.sidebar.text_input("Research Topic / Domain", "Agentic AI Frameworks")
competitor_query = st.sidebar.text_input("Competitors / Companies", "OpenAI, Anthropic, DeepMind")
max_items = st.sidebar.slider("Scan Depth (Items per source)", 2, 10, 5)

run_scan_btn = st.sidebar.button("🚀 Run Autonomous Scan", type="primary", use_container_width=True)

# Main Execution Trigger
if run_scan_btn or st.session_state.scan_results is None:
    with st.spinner("🤖 Autonomous Agent Scanning ArXiv Papers & Web News..."):
        papers = fetch_arxiv_papers(track_topic, max_results=max_items)
        news = fetch_competitor_news(competitor_query, max_results=max_items)
        
        st.session_state.scan_results = {
            "papers": papers,
            "news": news,
            "topic": track_topic,
            "competitor": competitor_query
        }
        
        brain = AgentRouterBrain(
            api_key=env_api_key,
            base_url=env_base_url,
            model=model_choice
        )
        
        st.session_state.executive_report = brain.generate_executive_digest(
            research_data=papers,
            competitor_data=news,
            topic=f"{track_topic} & {competitor_query}"
        )

# Metrics Bar
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Research Papers Found", len(st.session_state.scan_results["papers"]))
with col2:
    st.metric("Competitor Signals", len(st.session_state.scan_results["news"]))
with col3:
    status_text = "🟢 Active (Claude)" if api_key_input else "🟡 Fallback Engine"
    st.metric("Agent Engine Status", status_text)
with col4:
    st.metric("Tracked Domain", st.session_state.scan_results["topic"][:15] + "...")

st.divider()

# Navigation Tabs
tab_report, tab_research, tab_news, tab_chat = st.tabs([
    "📊 Executive Report", 
    "🔬 Research Publications", 
    "⚔️ Competitor News", 
    "💬 Analyst Chat"
])

# Tab 1: Executive Intelligence Digest
with tab_report:
    st.subheader("Synthesized Executive Intelligence Digest")
    if st.session_state.executive_report:
        st.markdown(st.session_state.executive_report)
        st.download_button(
            label="📥 Download Markdown Report",
            data=st.session_state.executive_report,
            file_name="intelpulse_executive_report.md",
            mime="text/markdown"
        )
    else:
        st.info("Run a scan to generate executive report.")

# Tab 2: ArXiv Papers
with tab_research:
    st.subheader(f"ArXiv Research Publications for '{st.session_state.scan_results['topic']}'")
    papers = st.session_state.scan_results["papers"]
    for p in papers:
        with st.expander(f"📄 {p['title']} ({p['published']})"):
            st.write(f"**Authors:** {', '.join(p['authors'])}")
            st.write(f"**Abstract Summary:** {p['summary']}")
            st.markdown(f"[🔗 View Original PDF]({p['pdf_url']})")

# Tab 3: Competitor News
with tab_news:
    st.subheader(f"Live Market & Competitor News for '{st.session_state.scan_results['competitor']}'")
    news = st.session_state.scan_results["news"]
    for n in news:
        with st.expander(f"📰 {n['title']} [{n['source_name']}]"):
            st.write(f"**Snippet:** {n['snippet']}")
            st.write(f"**Date:** {n['date']}")
            st.markdown(f"[🔗 Read Full Article]({n['url']})")

# Tab 4: Interactive Analyst Chat
with tab_chat:
    st.subheader("💬 Interactive Analyst Chat")
    st.caption("Ask questions about the scanned papers, competitor moves, or strategic implications.")
    
    # Display previous messages
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
    # Chat Input
    if user_prompt := st.chat_input("Ask IntelPulse Analyst a question..."):
        st.session_state.chat_history.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.markdown(user_prompt)
            
        brain = AgentRouterBrain(
            api_key=env_api_key,
            base_url=env_base_url,
            model=model_choice
        )
        
        with st.chat_message("assistant"):
            with st.spinner("Analyzing context..."):
                response = brain.ask_analyst_chat(
                    user_question=user_prompt,
                    context_research=st.session_state.scan_results["papers"],
                    context_competitors=st.session_state.scan_results["news"]
                )
                st.markdown(response)
                st.session_state.chat_history.append({"role": "assistant", "content": response})
