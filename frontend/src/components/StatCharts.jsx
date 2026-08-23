import React from 'react';
import { motion } from 'framer-motion';
import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  PolarAngleAxis,
  RadialBar,
  RadialBarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { CHART_COLORS, topDomains } from '../lib/sources';

/**
 * The statistics column: three charts over the same scan, each answering a
 * different question — what kind of evidence came back, which competitor the
 * signal concentrates on, and which domains actually served it.
 *
 * All three are recharts, so the entry tweens and hover states are real rather
 * than hand-rolled SVG. Every number traces to a finding the agent retrieved.
 */

const AXIS_STYLE = { fontSize: 9, fontFamily: '"JetBrains Mono", monospace', fill: '#6E7455' };

function GlassTooltip({ active, payload, suffix = 'signals' }) {
  if (!active || !payload?.length) return null;
  const point = payload[0];
  return (
    <div className="rounded-lg border border-white/80 bg-white/90 px-2.5 py-1.5 font-mono text-[10px] text-ink shadow-lift backdrop-blur">
      <span className="font-semibold">{point.payload.name}</span>
      <span className="ml-1.5 text-clay">
        {point.value} {suffix}
      </span>
    </div>
  );
}

function Empty({ label }) {
  return (
    <div className="flex h-full items-center justify-center px-4 text-center font-mono text-[10px] leading-relaxed text-ink/40">
      {label}
    </div>
  );
}

export default function StatCharts({ sourceData, competitorData, findings, coverage }) {
  const hasSignals = sourceData.length > 0;
  const domains = topDomains(findings, 4);

  return (
    <div className="flex min-h-0 flex-col gap-2.5">
      {/* SOURCE MIX — what kind of evidence the scan is standing on */}
      <div className="glass-inset flex min-h-0 flex-1 flex-col p-2.5">
        <div className="flex items-baseline justify-between">
          <h4 className="font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-ink/70">Evidence mix</h4>
          <span className="font-hand text-[13px] leading-none text-clay">by source type</span>
        </div>

        {hasSignals ? (
          <div className="flex min-h-0 flex-1 items-center">
            <div className="relative h-[104px] w-[104px] shrink-0">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={sourceData}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={30}
                    outerRadius={48}
                    paddingAngle={2}
                    stroke="rgba(255,255,255,0.85)"
                    strokeWidth={1.5}
                    animationDuration={900}
                  >
                    {sourceData.map((entry, i) => (
                      <Cell key={entry.name} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip content={<GlassTooltip />} />
                </PieChart>
              </ResponsiveContainer>
              <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                <span className="font-sans text-base font-bold leading-none text-ink">{findings.length}</span>
                <span className="font-mono text-[8px] uppercase tracking-widest text-ink/50">signals</span>
              </div>
            </div>

            <ul className="ml-1 grid min-w-0 flex-1 grid-cols-1 gap-y-[3px] font-mono text-[10px]">
              {sourceData.map((entry, i) => (
                <li key={entry.name} className="flex items-center justify-between gap-2">
                  <span className="flex min-w-0 items-center gap-1.5">
                    <span
                      className="h-2 w-2 shrink-0 rounded-full"
                      style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }}
                    />
                    <span className="truncate text-ink/80">{entry.name}</span>
                  </span>
                  <span className="font-semibold text-ink/55">{entry.value}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <Empty label="Evidence mix appears once a scan returns findings." />
        )}
      </div>

      {/* COMPETITOR SHARE — where the signal concentrates */}
      <div className="glass-inset flex min-h-0 flex-1 flex-col p-2.5">
        <div className="flex items-baseline justify-between">
          <h4 className="font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-ink/70">Competitor share</h4>
          <span className="font-hand text-[13px] leading-none text-moss">signal density</span>
        </div>

        {competitorData.some((d) => d.count > 0) ? (
          <div className="min-h-0 flex-1">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={competitorData} layout="vertical" margin={{ top: 6, right: 14, bottom: 0, left: 0 }}>
                <XAxis type="number" hide />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={62}
                  tick={AXIS_STYLE}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip content={<GlassTooltip />} cursor={{ fill: 'rgba(194,96,58,0.07)' }} />
                <Bar dataKey="count" radius={[0, 5, 5, 0]} barSize={11} animationDuration={950}>
                  {competitorData.map((entry, i) => (
                    <Cell key={entry.name} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <Empty label="Per-competitor density plots after the first scan." />
        )}
      </div>

      {/* PROVENANCE — the real domains behind the cards, with their own favicons */}
      <div className="glass-inset flex shrink-0 flex-col gap-1.5 p-2.5">
        <div className="flex items-baseline justify-between">
          <h4 className="font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-ink/70">Serving domains</h4>
          <span className="font-hand text-[13px] leading-none text-clay">who answered</span>
        </div>

        {domains.length > 0 ? (
          <ul className="space-y-1">
            {domains.map((d, i) => (
              <motion.li
                key={d.host}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.06, duration: 0.35 }}
                className="flex items-center gap-2 font-mono text-[10px]"
              >
                <img
                  src={d.favicon}
                  alt=""
                  loading="lazy"
                  className="h-3.5 w-3.5 shrink-0 rounded-[3px] bg-white/70 object-contain"
                  onError={(e) => {
                    e.currentTarget.style.visibility = 'hidden';
                  }}
                />
                <span className="min-w-0 flex-1 truncate text-ink/75">{d.host}</span>
                <span className="shrink-0 rounded bg-white/60 px-1.5 font-semibold text-ink/55">{d.count}</span>
              </motion.li>
            ))}
          </ul>
        ) : (
          <p className="py-1 font-mono text-[10px] text-ink/40">No domains served yet.</p>
        )}

        {/* Coverage: how many of the seven wired sources actually produced evidence. */}
        <div className="mt-0.5 flex items-center gap-2 border-t border-ink/10 pt-1.5">
          <div className="h-[42px] w-[42px] shrink-0">
            <ResponsiveContainer width="100%" height="100%">
              <RadialBarChart
                data={[{ name: 'Coverage', value: coverage.pct }]}
                innerRadius="66%"
                outerRadius="112%"
                startAngle={90}
                endAngle={-270}
              >
                <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
                <RadialBar dataKey="value" cornerRadius={8} fill="#4E7A6E" background={{ fill: 'rgba(42,39,35,0.10)' }} />
              </RadialBarChart>
            </ResponsiveContainer>
          </div>
          <div className="min-w-0 font-mono text-[10px] leading-tight text-ink/70">
            <span className="font-bold text-ink">
              {coverage.used}/{coverage.total}
            </span>{' '}
            wired sources returned evidence
          </div>
        </div>
      </div>
    </div>
  );
}
