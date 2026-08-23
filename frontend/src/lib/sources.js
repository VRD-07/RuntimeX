/**
 * Source vocabulary shared by the findings board, the charts and the chat payload.
 *
 * These lists mirror SECTION_ORDER / SECTION_RESPONSE_KEYS in backend/agent_brain.py.
 * They live here rather than in App.jsx so the filter bar, the charts and the
 * context payload cannot drift apart — they used to be three hardcoded lists.
 */

export const SOURCE_TYPES = ['news', 'research', 'patents', 'github', 'reddit', 'models', 'hackernews'];

export const SOURCE_LABELS = {
  news: 'News',
  research: 'Research',
  patents: 'Patents',
  github: 'GitHub',
  reddit: 'Reddit',
  models: 'Model Hub',
  hackernews: 'Hacker News',
};

// Flat top-level arrays in the scan response, read only when structured_output
// is missing (older backend builds).
export const SOURCE_RESPONSE_KEYS = {
  news: 'news',
  research: 'papers',
  patents: 'patents',
  github: 'github_repos',
  reddit: 'reddit_posts',
  models: 'hf_models',
  hackernews: 'hn_posts',
};

/*
  Chart palette, drawn from the warm editorial theme rather than generic chart
  primaries: clay, moss, ochre, ink-teal, plum, sand-brown, slate-olive. Ordered
  so adjacent slices in a donut never sit at the same value.
*/
export const CHART_COLORS = [
  '#C2603A', // clay / terracotta
  '#6E7455', // moss / olive
  '#D38B5D', // ochre
  '#4E7A6E', // deep teal
  '#8A6B7C', // plum
  '#A8763F', // bronze
  '#8C9270', // sage
];

export const SOURCE_COLORS = SOURCE_TYPES.reduce((acc, type, i) => {
  acc[type] = CHART_COLORS[i % CHART_COLORS.length];
  return acc;
}, {});

/** Hostname of a finding's URL, or null when the URL is missing or unparseable. */
export function hostOf(url) {
  if (!url) return null;
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return null;
  }
}

/**
 * Favicon for a finding's own domain. The imagery on the board is therefore
 * derived from the retrieved data — never a stock illustration standing in for
 * a source that was not actually consulted.
 */
export function faviconOf(url, size = 64) {
  const host = hostOf(url);
  return host ? `https://www.google.com/s2/favicons?domain=${host}&sz=${size}` : null;
}

/** The domains that produced the most findings, for the source-provenance list. */
export function topDomains(findings, limit = 5) {
  const counts = new Map();
  findings.forEach((f) => {
    const host = hostOf(f.url);
    if (!host) return;
    counts.set(host, (counts.get(host) || 0) + 1);
  });
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([host, count]) => ({ host, count, favicon: `https://www.google.com/s2/favicons?domain=${host}&sz=64` }));
}
