import React, { useEffect, useRef } from 'react';
import { animate, useInView, useMotionValue } from 'framer-motion';

/**
 * A statistic that counts up to its value instead of snapping to it.
 *
 * The tween runs on a motion value and writes to the node directly, so a scan
 * streaming sixty findings in does not re-render the React tree sixty times.
 */
export default function Counter({ value = 0, duration = 0.9, className = '' }) {
  const node = useRef(null);
  const inView = useInView(node, { once: false });
  const motionValue = useMotionValue(0);

  useEffect(() => {
    if (!inView) return undefined;
    const controls = animate(motionValue, value, {
      duration,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (v) => {
        if (node.current) node.current.textContent = Math.round(v).toLocaleString();
      },
    });
    return () => controls.stop();
  }, [value, duration, inView, motionValue]);

  // Rendered with the target value so the number is correct before JS animates and
  // for anything reading the DOM (tests, screen readers).
  return (
    <span ref={node} className={className}>
      {value.toLocaleString()}
    </span>
  );
}
