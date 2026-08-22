import React, { useState } from 'react';
import { API_BASE_URL } from '../api';

export default function AgentDebugView() {
  const [userRequest, setUserRequest] = useState(
    'Track research trends, patent filings, news updates, and GitHub activity for Dating Apps (Tinder & Bumble)'
  );
  const [model, setModel] = useState('claude-3-5-sonnet');
  const [maxSteps, setMaxSteps] = useState(5);
  
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleRunAgent = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch(`${API_BASE_URL}/api/agent/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_request: userRequest,
          model: model,
          max_steps: parseInt(maxSteps)
        })
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: 'API call failed' }));
        throw new Error(errData.detail || `HTTP ${res.status}`);
      }

      const data = await res.json();
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '24px', fontFamily: 'monospace', backgroundColor: '#1e293b', color: '#f8fafc', minHeight: '100vh' }}>
      <div style={{ maxWidth: '1000px', margin: '0 auto' }}>
        
        {/* Header & Navigation */}
        <div style={{ borderBottom: '1px solid #334155', paddingBottom: '16px', marginBottom: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h1 style={{ margin: 0, fontSize: '20px', color: '#38bdf8' }}>🛠️ Agent Debug Console</h1>
            <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#94a3b8' }}>Standalone ReAct Agent Trace & Tool Inspection Tool (/debug/agent)</p>
          </div>
          <a href="/" style={{ color: '#38bdf8', fontSize: '13px', textDecoration: 'underline' }}>← Back to Main App</a>
        </div>

        {/* Input Controls Form */}
        <form onSubmit={handleRunAgent} style={{ backgroundColor: '#0f172a', padding: '16px', borderRadius: '8px', border: '1px solid #334155', marginBottom: '24px' }}>
          <div style={{ marginBottom: '12px' }}>
            <label style={{ display: 'block', fontSize: '12px', color: '#cbd5e1', marginBottom: '6px' }}>User Query / Request:</label>
            <input
              type="text"
              value={userRequest}
              onChange={(e) => setUserRequest(e.target.value)}
              style={{ width: '100%', padding: '8px 12px', backgroundColor: '#1e293b', border: '1px solid #475569', color: '#fff', borderRadius: '4px', fontSize: '13px' }}
              required
            />
          </div>

          <div style={{ display: 'flex', gap: '16px', marginBottom: '16px' }}>
            <div style={{ flex: 1 }}>
              <label style={{ display: 'block', fontSize: '12px', color: '#cbd5e1', marginBottom: '4px' }}>Model:</label>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                style={{ width: '100%', padding: '6px 10px', backgroundColor: '#1e293b', border: '1px solid #475569', color: '#fff', borderRadius: '4px', fontSize: '12px' }}
              >
                <option value="claude-3-5-sonnet">Claude 3.5 Sonnet</option>
                <option value="claude-3-7-sonnet">Claude 3.7 Sonnet</option>
                <option value="claude-3-5-haiku">Claude 3.5 Haiku</option>
                <option value="gpt-4o">GPT-4o</option>
                <option value="deepseek-r1">DeepSeek R1</option>
              </select>
            </div>

            <div style={{ width: '150px' }}>
              <label style={{ display: 'block', fontSize: '12px', color: '#cbd5e1', marginBottom: '4px' }}>Max Steps:</label>
              <input
                type="number"
                min="1"
                max="10"
                value={maxSteps}
                onChange={(e) => setMaxSteps(e.target.value)}
                style={{ width: '100%', padding: '6px 10px', backgroundColor: '#1e293b', border: '1px solid #475569', color: '#fff', borderRadius: '4px', fontSize: '12px' }}
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{ backgroundColor: '#0284c7', color: '#fff', padding: '10px 20px', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold', fontSize: '13px', width: '100%' }}
          >
            {loading ? '⏳ Running ReAct Agent Loop...' : '🚀 Run Agent'}
          </button>
        </form>

        {/* Error Notification */}
        {error && (
          <div style={{ backgroundColor: '#7f1d1d', color: '#fca5a5', padding: '12px 16px', borderRadius: '6px', marginBottom: '24px', fontSize: '13px', border: '1px solid #f87171' }}>
            ⚠️ Error: {error}
          </div>
        )}

        {/* Results Panel */}
        {result && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            
            {/* 1. Step-by-Step Thought/Action/Observation Trace */}
            <div style={{ backgroundColor: '#0f172a', padding: '16px', borderRadius: '8px', border: '1px solid #334155' }}>
              <h2 style={{ fontSize: '15px', color: '#38bdf8', margin: '0 0 12px 0', borderBottom: '1px solid #334155', paddingBottom: '8px' }}>
                1. Step-by-Step ReAct Trace ({result.trace?.length || 0} Steps)
              </h2>

              {result.trace?.map((step, idx) => (
                <div key={idx} style={{ marginBottom: '16px', padding: '12px', backgroundColor: '#1e293b', borderRadius: '6px', borderLeft: '4px solid #38bdf8' }}>
                  <div style={{ fontWeight: 'bold', color: '#fbbf24', fontSize: '13px', marginBottom: '6px' }}>
                    Step {step.step || idx + 1}
                  </div>
                  
                  <div style={{ marginBottom: '6px', fontSize: '12px' }}>
                    <span style={{ color: '#a7f3d0', fontWeight: 'bold' }}>Thought: </span>
                    <span style={{ color: '#e2e8f0' }}>{step.thought}</span>
                  </div>

                  <div style={{ marginBottom: '6px', fontSize: '12px' }}>
                    <span style={{ color: '#f472b6', fontWeight: 'bold' }}>Action: </span>
                    <code style={{ backgroundColor: '#0f172a', padding: '2px 6px', borderRadius: '3px', color: '#f472b6' }}>{step.action}</code>
                  </div>

                  <div style={{ fontSize: '12px' }}>
                    <span style={{ color: '#60a5fa', fontWeight: 'bold' }}>Observation: </span>
                    <pre style={{ backgroundColor: '#0f172a', padding: '8px', borderRadius: '4px', color: '#cbd5e1', overflowX: 'auto', whiteSpace: 'pre-wrap', marginTop: '4px', fontSize: '11px' }}>
                      {step.observation}
                    </pre>
                  </div>
                </div>
              ))}
            </div>

            {/* 2. Raw JSON Returned by Each Individual Tool Call */}
            <div style={{ backgroundColor: '#0f172a', padding: '16px', borderRadius: '8px', border: '1px solid #334155' }}>
              <h2 style={{ fontSize: '15px', color: '#38bdf8', margin: '0 0 12px 0', borderBottom: '1px solid #334155', paddingBottom: '8px' }}>
                2. Raw Tool Response JSON Payload
              </h2>
              <pre style={{ backgroundColor: '#1e293b', padding: '12px', borderRadius: '6px', color: '#4ade80', overflowX: 'auto', fontSize: '11px', maxHeight: '350px' }}>
                {JSON.stringify(result.trace, null, 2)}
              </pre>
            </div>

            {/* 3. Final Answer Text at the Bottom */}
            <div style={{ backgroundColor: '#0f172a', padding: '16px', borderRadius: '8px', border: '1px solid #38bdf8' }}>
              <h2 style={{ fontSize: '15px', color: '#4ade80', margin: '0 0 12px 0', borderBottom: '1px solid #334155', paddingBottom: '8px' }}>
                3. Final Answer (Grounded Output)
              </h2>
              <pre style={{ backgroundColor: '#1e293b', padding: '16px', borderRadius: '6px', color: '#f8fafc', overflowX: 'auto', whiteSpace: 'pre-wrap', fontSize: '12px', lineHeight: '1.6' }}>
                {result.final_answer}
              </pre>
            </div>

          </div>
        )}

      </div>
    </div>
  );
}
