// Decoupled API Service Layer for IntelPulse Backend
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE_URL}/api/health`);
    if (!res.ok) throw new Error('Health check failed');
    return await res.json();
  } catch (err) {
    console.error('API Health Error:', err);
    return { status: 'offline', agentrouter_active: false };
  }
}

export async function runScan(topic, competitors, maxItems = 5, model = 'claude-3-5-sonnet') {
  const res = await fetch(`${API_BASE_URL}/api/scan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      topic,
      competitors,
      max_items: maxItems,
      model
    })
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: 'Scan failed' }));
    throw new Error(errorData.detail || 'Scan failed');
  }

  return await res.json();
}

export async function sendChatMessage(question, contextResearch = [], contextCompetitors = [], model = 'claude-3-5-sonnet') {
  const res = await fetch(`${API_BASE_URL}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question,
      context_research: contextResearch,
      context_competitors: contextCompetitors,
      model
    })
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: 'Chat request failed' }));
    throw new Error(errorData.detail || 'Chat failed');
  }

  return await res.json();
}
