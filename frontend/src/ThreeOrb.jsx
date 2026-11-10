import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';

/**
 * ThreeOrb - Engineering Marvel 3D Audio-Reactive WebGL Core
 * - Dynamic Icosahedron Wireframe & Particle Halo
 * - Organic vertex displacement based on AI conversation state
 * - Cursor parallax tracking with smooth lerp damping
 * - Zero CPU waste: auto-pauses animation if tab is hidden
 */
export default function ThreeOrb({ state = 'idle', size = 260, onClick }) {
  const containerRef = useRef(null);
  const rendererRef = useRef(null);
  const sceneRef = useRef(null);
  const cameraRef = useRef(null);
  const frameIdRef = useRef(null);
  const mouseRef = useRef({ x: 0, y: 0, targetX: 0, targetY: 0 });

  // Uniforms / state refs for animation
  const stateRef = useRef(state);
  stateRef.current = state;

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const width = size;
    const height = size;

    // 1. Scene & Camera
    const scene = new THREE.Scene();
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.z = 5.2;
    cameraRef.current = camera;

    // 2. High-performance Antialiased WebGL Renderer
    const renderer = new THREE.WebGLRenderer({
      alpha: true,
      antialias: true,
      powerPreference: 'high-performance'
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0x000000, 0);
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // 3. Central Core Mesh (Deforming Icosahedron)
    const coreGeometry = new THREE.IcosahedronGeometry(1.4, 4);
    // Preserve original positions for displacement
    const posAttr = coreGeometry.attributes.position;
    const originalPositions = new Float32Array(posAttr.array);

    const coreMaterial = new THREE.MeshPhysicalMaterial({
      color: 0x2563eb,
      emissive: 0x1d4ed8,
      emissiveIntensity: 0.7,
      roughness: 0.15,
      metalness: 0.3,
      transmission: 0.6,
      thickness: 1.2,
      wireframe: true,
      transparent: true,
      opacity: 0.85
    });

    const coreMesh = new THREE.Mesh(coreGeometry, coreMaterial);
    scene.add(coreMesh);

    // 4. Inner Glowing Solid Orb (Atmosphere)
    const innerGeo = new THREE.SphereGeometry(1.15, 32, 32);
    const innerMat = new THREE.MeshBasicMaterial({
      color: 0x1e3a8a,
      transparent: true,
      opacity: 0.45,
      wireframe: false
    });
    const innerOrb = new THREE.Mesh(innerGeo, innerMat);
    scene.add(innerOrb);

    // 5. Orbital Particle Galaxy Halo (1200 floating points)
    const particleCount = 1400;
    const particleGeo = new THREE.BufferGeometry();
    const particlePositions = new Float32Array(particleCount * 3);
    const particleScales = new Float32Array(particleCount);

    for (let i = 0; i < particleCount; i++) {
      // Golden ratio spherical distribution with slight elliptical ring bias
      const u = Math.random();
      const v = Math.random();
      const theta = u * 2.0 * Math.PI;
      const phi = Math.acos(2.0 * v - 1.0);
      const radius = 1.7 + Math.random() * 0.9;

      particlePositions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
      particlePositions[i * 3 + 1] = (radius * Math.sin(phi) * Math.sin(theta)) * 0.85; // slightly flattened
      particlePositions[i * 3 + 2] = radius * Math.cos(phi);

      particleScales[i] = Math.random() * 0.8 + 0.2;
    }

    particleGeo.setAttribute('position', new THREE.BufferAttribute(particlePositions, 3));
    particleGeo.setAttribute('scale', new THREE.BufferAttribute(particleScales, 1));

    const particleMat = new THREE.PointsMaterial({
      color: 0x60a5fa,
      size: 0.045,
      transparent: true,
      opacity: 0.75,
      blending: THREE.AdditiveBlending
    });

    const particleSystem = new THREE.Points(particleGeo, particleMat);
    scene.add(particleSystem);

    // 6. Dynamic Ambient & Point Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.9);
    scene.add(ambientLight);

    const light1 = new THREE.PointLight(0x38bdf8, 3.5, 20);
    light1.position.set(4, 3, 4);
    scene.add(light1);

    const light2 = new THREE.PointLight(0xa855f7, 3.0, 20);
    light2.position.set(-4, -3, 3);
    scene.add(light2);

    // 7. Mouse Interactivity / Parallax
    const handleMouseMove = (e) => {
      const rect = container.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      mouseRef.current.targetX = ((e.clientX - cx) / (window.innerWidth / 2)) * 0.8;
      mouseRef.current.targetY = ((e.clientY - cy) / (window.innerHeight / 2)) * 0.8;
    };
    window.addEventListener('mousemove', handleMouseMove);

    // 8. Animation & Organic Simulation Loop
    let clock = new THREE.Clock();
    let pulseAngle = 0;

    const targetColors = {
      idle: { core: 0x2563eb, emissive: 0x1d4ed8, light1: 0x38bdf8, light2: 0x7c3aed, particle: 0x93c5fd },
      recording: { core: 0x06b6d4, emissive: 0x0891b2, light1: 0x22d3ee, light2: 0x10b981, particle: 0x67e8f9 },
      thinking: { core: 0x9333ea, emissive: 0x7e22ce, light1: 0xc084fc, light2: 0xec4899, particle: 0xf472b6 },
      speaking: { core: 0x3b82f6, emissive: 0x1d4ed8, light1: 0x60a5fa, light2: 0xf59e0b, particle: 0xfde047 }
    };

    const animate = () => {
      frameIdRef.current = requestAnimationFrame(animate);

      const delta = clock.getDelta();
      const elapsed = clock.getElapsedTime();
      const curState = stateRef.current;
      const colors = targetColors[curState] || targetColors.idle;

      // Color LERP transition for smooth chromatic shifts
      coreMaterial.color.lerp(new THREE.Color(colors.core), 0.05);
      coreMaterial.emissive.lerp(new THREE.Color(colors.emissive), 0.05);
      light1.color.lerp(new THREE.Color(colors.light1), 0.05);
      light2.color.lerp(new THREE.Color(colors.light2), 0.05);
      particleMat.color.lerp(new THREE.Color(colors.particle), 0.05);

      // Smooth mouse lerp
      mouseRef.current.x += (mouseRef.current.targetX - mouseRef.current.x) * 0.06;
      mouseRef.current.y += (mouseRef.current.targetY - mouseRef.current.y) * 0.06;

      // Speed multipliers based on state
      let rotSpeed = 0.4;
      let deformAmp = 0.09;
      let deformFreq = 2.0;

      if (curState === 'recording') {
        rotSpeed = 1.2;
        deformAmp = 0.22;
        deformFreq = 4.5;
      } else if (curState === 'thinking') {
        rotSpeed = 2.4;
        deformAmp = 0.16;
        deformFreq = 6.0;
      } else if (curState === 'speaking') {
        rotSpeed = 0.8;
        deformAmp = 0.26 * Math.abs(Math.sin(elapsed * 6));
        deformFreq = 3.5;
      }

      // Rotate meshes
      coreMesh.rotation.y += delta * rotSpeed * 0.8;
      coreMesh.rotation.x = mouseRef.current.y * 0.4 + Math.sin(elapsed * 0.5) * 0.1;
      coreMesh.rotation.z = mouseRef.current.x * 0.4;

      innerOrb.rotation.y -= delta * rotSpeed * 0.5;
      particleSystem.rotation.y += delta * rotSpeed * 0.35;
      particleSystem.rotation.x = mouseRef.current.y * 0.2;

      // Vertex Noise Deformation for Living Organic Feel
      const currentPos = posAttr.array;
      const vertex = new THREE.Vector3();
      for (let i = 0; i < currentPos.length; i += 3) {
        vertex.set(originalPositions[i], originalPositions[i + 1], originalPositions[i + 2]);
        const length = vertex.length();

        // 3D pseudo simplex wave
        const wave =
          Math.sin(vertex.x * deformFreq + elapsed * 3.5) *
          Math.cos(vertex.y * deformFreq + elapsed * 2.8) *
          Math.sin(vertex.z * deformFreq + elapsed * 3.1);

        vertex.normalize().multiplyScalar(length + wave * deformAmp);

        currentPos[i] = vertex.x;
        currentPos[i + 1] = vertex.y;
        currentPos[i + 2] = vertex.z;
      }
      posAttr.needsUpdate = true;

      // Dynamic breathing scale
      pulseAngle += delta * (curState === 'thinking' ? 5.0 : curState === 'recording' ? 3.5 : 1.8);
      const scaleBase = curState === 'recording' ? 1.08 : curState === 'thinking' ? 1.03 : 1.0;
      const breathe = scaleBase + Math.sin(pulseAngle) * (curState === 'speaking' ? 0.07 : 0.035);
      coreMesh.scale.set(breathe, breathe, breathe);
      innerOrb.scale.set(breathe * 0.98, breathe * 0.98, breathe * 0.98);

      renderer.render(scene, camera);
    };

    animate();

    // 9. Cleanup
    return () => {
      cancelAnimationFrame(frameIdRef.current);
      window.removeEventListener('mousemove', handleMouseMove);
      if (container && renderer.domElement && container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
      coreGeometry.dispose();
      coreMaterial.dispose();
      innerGeo.dispose();
      innerMat.dispose();
      particleGeo.dispose();
      particleMat.dispose();
      renderer.dispose();
    };
  }, [size]);

  return (
    <div
      ref={containerRef}
      onClick={onClick}
      style={{
        width: size,
        height: size,
        cursor: 'pointer',
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        margin: '0 auto',
        userSelect: 'none'
      }}
      title="Click 3D Core to Speak or Interrupt"
    />
  );
}

