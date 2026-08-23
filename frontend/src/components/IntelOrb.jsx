import React, { useMemo, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';

/**
 * The signal core: a real 3D object, not an illustration of one.
 *
 * Point count is derived from how many findings the scan actually returned, so a
 * thin scan produces a sparse shell and a rich one a dense cloud — the geometry is
 * a readout, not decoration. The wireframe icosahedron inside gives the cloud a
 * visible interior so the rotation is legible, and the whole rig spins faster while
 * the agent is mid-scan.
 */

/** Fibonacci sphere: even coverage without the pole clustering of naive lat/long. */
function sphereShell(count, radius) {
  const positions = new Float32Array(count * 3);
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < count; i++) {
    const y = 1 - (i / Math.max(count - 1, 1)) * 2;
    const r = Math.sqrt(Math.max(0, 1 - y * y));
    const theta = golden * i;
    // A little jitter so the lattice does not read as a printed pattern.
    const jitter = 0.94 + ((i * 37) % 13) / 100;
    positions[i * 3] = Math.cos(theta) * r * radius * jitter;
    positions[i * 3 + 1] = y * radius * jitter;
    positions[i * 3 + 2] = Math.sin(theta) * r * radius * jitter;
  }
  return positions;
}

function Core({ findings, active }) {
  const cloud = useRef();
  const frame = useRef();

  // 320 points at rest, growing with the findings actually retrieved.
  const count = Math.min(1600, 320 + findings * 16);
  const positions = useMemo(() => sphereShell(count, 1.28), [count]);

  useFrame((state, delta) => {
    const spin = active ? 0.85 : 0.22;
    if (cloud.current) {
      cloud.current.rotation.y += delta * spin;
      cloud.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.28) * 0.28;
      const pulse = 1 + (active ? Math.sin(state.clock.elapsedTime * 3.1) * 0.045 : 0);
      cloud.current.scale.setScalar(pulse);
    }
    if (frame.current) {
      frame.current.rotation.y -= delta * (spin * 0.55);
      frame.current.rotation.z += delta * 0.08;
    }
  });

  return (
    <group>
      <points ref={cloud}>
        {/* Keyed on count so the buffer is rebuilt when the scan size changes. */}
        <bufferGeometry key={count}>
          <bufferAttribute attach="attributes-position" array={positions} count={count} itemSize={3} />
        </bufferGeometry>
        <pointsMaterial
          size={0.045}
          sizeAttenuation
          color={active ? '#C2603A' : '#6E7455'}
          transparent
          opacity={0.92}
        />
      </points>

      <mesh ref={frame}>
        <icosahedronGeometry args={[0.78, 1]} />
        <meshBasicMaterial color="#C2603A" wireframe transparent opacity={0.32} />
      </mesh>

      <mesh>
        <sphereGeometry args={[0.42, 24, 24]} />
        <meshBasicMaterial color="#EAE3D2" transparent opacity={0.55} />
      </mesh>
    </group>
  );
}

export default function IntelOrb({ findings = 0, active = false, className = '' }) {
  return (
    <div className={className} aria-hidden="true">
      <Canvas
        camera={{ position: [0, 0, 3.4], fov: 45 }}
        gl={{ alpha: true, antialias: true, powerPreference: 'low-power' }}
        dpr={[1, 2]}
      >
        <Core findings={findings} active={active} />
      </Canvas>
    </div>
  );
}
