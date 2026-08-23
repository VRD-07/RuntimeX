import React, { useRef, useState } from 'react';
import { motion, useMotionTemplate, useMotionValue, useSpring, useTransform } from 'framer-motion';
import { ExternalLink, Globe } from 'lucide-react';

import { SOURCE_COLORS, SOURCE_LABELS, faviconOf, hostOf } from '../lib/sources';

/**
 * One finding, as a glass card that actually tilts in 3D.
 *
 * The tilt is a perspective transform driven by the pointer's position inside the
 * card and smoothed through springs, with a specular sheen tracking the same
 * position — the card behaves like a physical pane catching light, which is what
 * makes glass read as glass rather than as a translucent rectangle.
 *
 * Every card carries the favicon of the domain it came from, so the imagery on the
 * board is drawn from the retrieved evidence rather than decorating it.
 */

const SPRING = { stiffness: 260, damping: 22, mass: 0.6 };

export default function FindingCard({ item, topic, index = 0 }) {
  const ref = useRef(null);
  const [iconFailed, setIconFailed] = useState(false);

  // -0.5 .. 0.5 across each axis of the card.
  const px = useMotionValue(0);
  const py = useMotionValue(0);
  const rotateX = useSpring(useTransform(py, [-0.5, 0.5], ['7.5deg', '-7.5deg']), SPRING);
  const rotateY = useSpring(useTransform(px, [-0.5, 0.5], ['-9deg', '9deg']), SPRING);
  const sheenX = useTransform(px, [-0.5, 0.5], ['12%', '88%']);
  const sheenY = useTransform(py, [-0.5, 0.5], ['6%', '94%']);
  const sheen = useMotionTemplate`radial-gradient(circle at ${sheenX} ${sheenY}, rgba(255,255,255,0.55), rgba(255,255,255,0) 58%)`;

  const handleMove = (e) => {
    const rect = ref.current?.getBoundingClientRect();
    if (!rect) return;
    px.set((e.clientX - rect.left) / rect.width - 0.5);
    py.set((e.clientY - rect.top) / rect.height - 0.5);
  };

  const reset = () => {
    px.set(0);
    py.set(0);
  };

  const isSpecificCompetitor = item.entity && item.entity !== 'General' && item.entity !== topic;
  const accent = SOURCE_COLORS[item.source_type] || '#6E7455';
  const favicon = faviconOf(item.url);
  const host = hostOf(item.url);

  return (
    <motion.article
      ref={ref}
      onPointerMove={handleMove}
      onPointerLeave={reset}
      initial={{ opacity: 0, y: 14, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{
        // Capped so a sixty-card board still settles in well under a second.
        delay: Math.min(index, 24) * 0.022,
        duration: 0.42,
        ease: [0.22, 1, 0.36, 1],
      }}
      style={{ rotateX, rotateY, transformStyle: 'preserve-3d', transformPerspective: 900 }}
      whileHover={{ z: 26 }}
      className="glass-card group relative flex h-full flex-col p-3"
    >
      {/* Specular sheen, tracking the pointer. */}
      <motion.span
        aria-hidden="true"
        style={{ backgroundImage: sheen }}
        className="pointer-events-none absolute inset-0 rounded-[inherit] opacity-0 transition-opacity duration-300 group-hover:opacity-100"
      />

      {/* Source-type spine: colour-codes the card without adding another chip. */}
      <span
        aria-hidden="true"
        className="absolute left-0 top-3 bottom-3 w-[3px] rounded-full"
        style={{ backgroundColor: accent, opacity: 0.75 }}
      />

      <div className="relative flex min-w-0 flex-1 flex-col pl-2">
        <header className="flex items-center gap-1.5">
          {favicon && !iconFailed ? (
            <img
              src={favicon}
              alt=""
              loading="lazy"
              onError={() => setIconFailed(true)}
              className="h-4 w-4 shrink-0 rounded-[3px] bg-white/80 object-contain"
            />
          ) : (
            <Globe className="h-3.5 w-3.5 shrink-0 text-ink/35" />
          )}

          <span
            className={`truncate rounded px-1.5 py-[1px] font-mono text-[9px] font-bold uppercase tracking-wider ${
              isSpecificCompetitor ? 'bg-clay/15 text-clay' : 'bg-ink/[0.07] text-ink/55'
            }`}
          >
            {item.entity || 'Market'}
          </span>

          <span
            className="ml-auto shrink-0 font-mono text-[9px] font-semibold uppercase tracking-wider"
            style={{ color: accent }}
          >
            {SOURCE_LABELS[item.source_type] || item.source_type}
          </span>
        </header>

        <h4 className="mt-1.5 line-clamp-2 font-sans text-[12px] font-semibold leading-snug text-ink">
          {item.title}
        </h4>

        <p className="mt-1 line-clamp-3 font-sans text-[11px] leading-relaxed text-ink/60">{item.snippet}</p>

        <footer className="mt-auto flex items-center justify-between gap-2 pt-2 font-mono text-[9px] text-ink/45">
          <span className="truncate">{host || item.source_name}</span>
          <a
            href={item.url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex shrink-0 items-center gap-1 font-semibold text-clay transition-colors hover:text-clay-deep"
          >
            {item.date}
            <ExternalLink className="h-2.5 w-2.5" />
          </a>
        </footer>
      </div>
    </motion.article>
  );
}
