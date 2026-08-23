import React, { useMemo, useRef } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';

/**
 * Animated dot-grid shader that sits behind the whole dashboard.
 *
 * It is a real GLSL fragment shader on a single full-screen quad, not a repeating
 * PNG: the dot radius is driven by a travelling radial wave, so the grid breathes
 * slowly, and the pointer lifts the dots nearest the cursor. Colours are the warm
 * clay/moss pair from the theme at low alpha, so the grid reads as paper texture
 * under the glass panels rather than as decoration competing with them.
 *
 * The canvas is transparent, fixed, and pointer-events:none — the layout above it
 * never has to know it exists.
 */

const vertexShader = /* glsl */ `
  // The quad is already in clip space, so the camera is bypassed entirely and the
  // plane always covers the viewport regardless of resize.
  void main() {
    gl_Position = vec4(position.xy, 0.0, 1.0);
  }
`;

const fragmentShader = /* glsl */ `
  precision highp float;

  uniform vec2  uResolution;   // drawing-buffer size, in device pixels
  uniform vec2  uPointer;      // pointer position, in device pixels
  uniform float uTime;
  uniform float uSpacing;      // grid pitch, in device pixels
  uniform float uActivity;     // 0 idle .. 1 scan running
  uniform vec3  uColorA;
  uniform vec3  uColorB;

  void main() {
    vec2 px = gl_FragCoord.xy;
    vec2 uv = px / uResolution;

    // Distance to the centre of this cell: one dot per cell.
    vec2 cell = mod(px, uSpacing) - uSpacing * 0.5;
    float d = length(cell);

    // A wave travelling out from the upper left makes the grid breathe. It runs
    // faster and deeper while the agent is working, so the background carries the
    // same signal as the status pill.
    float ripple = sin(length(uv - vec2(0.16, 0.92)) * 13.0 - uTime * (0.55 + uActivity * 0.85));
    float wave = ripple * 0.5 + 0.5;

    float radius = mix(1.05, 2.5 + uActivity * 0.8, wave);
    float dot = smoothstep(radius, radius - 1.15, d);

    // Pointer spotlight: nearby dots grow and brighten.
    float near = 1.0 - smoothstep(0.0, 260.0 * (uResolution.y / 900.0), length(px - uPointer));
    dot = max(dot, smoothstep(radius + near * 1.9, radius - 1.15, d));

    // Fade toward the bottom right so the grid never fights the content column.
    float falloff = 1.0 - smoothstep(0.15, 1.25, length(uv - vec2(0.22, 0.86)));

    vec3 color = mix(uColorA, uColorB, wave * 0.85);
    float alpha = dot * (0.17 + 0.30 * near + 0.10 * uActivity) * (0.35 + 0.65 * falloff);

    gl_FragColor = vec4(color, alpha);
  }
`;

function DotField({ activity }) {
  const material = useRef();
  const { size, viewport } = useThree();

  const uniforms = useMemo(
    () => ({
      uResolution: { value: [1, 1] },
      uPointer: { value: [-1000, -1000] },
      uTime: { value: 0 },
      uSpacing: { value: 26 },
      uActivity: { value: 0 },
      // #C2603A clay and #6E7455 moss, linearised by hand to sRGB floats.
      uColorA: { value: [0.76, 0.38, 0.23] },
      uColorB: { value: [0.43, 0.46, 0.33] },
    }),
    []
  );

  // Pointer is tracked on the window, because the canvas itself takes no events.
  const pointer = useRef([-1000, -1000]);
  React.useEffect(() => {
    const onMove = (e) => {
      const dpr = window.devicePixelRatio || 1;
      // gl_FragCoord counts from the bottom left, the DOM from the top left.
      pointer.current = [e.clientX * dpr, (window.innerHeight - e.clientY) * dpr];
    };
    window.addEventListener('pointermove', onMove);
    return () => window.removeEventListener('pointermove', onMove);
  }, []);

  useFrame((state, delta) => {
    const u = material.current?.uniforms;
    if (!u) return;
    const dpr = viewport.dpr || 1;
    u.uTime.value += delta;
    u.uResolution.value = [size.width * dpr, size.height * dpr];
    u.uSpacing.value = 26 * dpr;
    u.uPointer.value = pointer.current;
    // Eased so the background does not snap when a scan starts or finishes.
    u.uActivity.value += ((activity ? 1 : 0) - u.uActivity.value) * Math.min(1, delta * 2.5);
  });

  return (
    <mesh frustumCulled={false}>
      <planeGeometry args={[2, 2]} />
      <shaderMaterial
        ref={material}
        uniforms={uniforms}
        vertexShader={vertexShader}
        fragmentShader={fragmentShader}
        transparent
        depthTest={false}
        depthWrite={false}
      />
    </mesh>
  );
}

export default function DotShaderBackground({ active = false }) {
  return (
    <div className="pointer-events-none fixed inset-0 z-0" aria-hidden="true">
      <Canvas
        gl={{ alpha: true, antialias: false, powerPreference: 'low-power' }}
        dpr={[1, 2]}
        // The shader is cheap but it is still a background: never let it push the
        // main thread on a low-end machine.
        frameloop="always"
      >
        <DotField activity={active} />
      </Canvas>
    </div>
  );
}
