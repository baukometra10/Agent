"use client";

import { useEffect, useRef } from "react";

type Props = {
  active?: boolean;
  intensity?: number;
  className?: string;
};

type Node = { x: number; y: number; r: number; phase: number; layer: number };
type Edge = { a: number; b: number };

export function NeuralNet({ active = false, intensity = 0.3, className = "" }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const state = useRef({ nodes: [] as Node[], edges: [] as Edge[], t: 0 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.max(1, Math.floor(rect.width * dpr));
      canvas.height = Math.max(1, Math.floor(rect.height * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      const w = rect.width;
      const h = rect.height;
      const layers = [6, 9, 11, 9, 6];
      const nodes: Node[] = [];
      layers.forEach((count, layer) => {
        for (let i = 0; i < count; i++) {
          nodes.push({
            x: (w * (layer + 0.7)) / (layers.length + 0.4),
            y: (h * (i + 1)) / (count + 1),
            r: 2.4 + (layer === 2 ? 1.4 : 0),
            phase: Math.random() * Math.PI * 2,
            layer,
          });
        }
      });
      const edges: Edge[] = [];
      let offset = 0;
      for (let layer = 0; layer < layers.length - 1; layer++) {
        const a0 = offset;
        const a1 = offset + layers[layer];
        const b0 = a1;
        const b1 = a1 + layers[layer + 1];
        for (let a = a0; a < a1; a++) {
          for (let b = b0; b < b1; b++) {
            if ((a + b) % 3 !== 0) edges.push({ a, b });
          }
        }
        offset = a1;
      }
      state.current.nodes = nodes;
      state.current.edges = edges;
    };

    resize();
    const onResize = () => resize();
    window.addEventListener("resize", onResize);

    let raf = 0;
    const draw = () => {
      const rect = canvas.getBoundingClientRect();
      const w = rect.width;
      const h = rect.height;
      state.current.t += active ? 0.035 + intensity * 0.04 : 0.008;
      const t = state.current.t;
      const { nodes, edges } = state.current;

      ctx.clearRect(0, 0, w, h);
      const glow = active ? 0.22 + intensity * 0.35 : 0.08;
      const g = ctx.createRadialGradient(w * 0.55, h * 0.5, 10, w * 0.55, h * 0.5, w * 0.55);
      g.addColorStop(0, `rgba(92,225,255,${glow})`);
      g.addColorStop(0.45, `rgba(79,124,255,${glow * 0.35})`);
      g.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, w, h);

      for (const e of edges) {
        const a = nodes[e.a];
        const b = nodes[e.b];
        const pulse = 0.5 + 0.5 * Math.sin(t * 2 + a.phase + b.phase);
        const alpha = active ? 0.08 + pulse * (0.18 + intensity * 0.25) : 0.04 + pulse * 0.04;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.strokeStyle = `rgba(124, 168, 255, ${alpha})`;
        ctx.lineWidth = active ? 1.1 : 0.7;
        ctx.stroke();

        if (active && pulse > 0.85) {
          const u = (t * 0.35 + a.phase) % 1;
          const x = a.x + (b.x - a.x) * u;
          const y = a.y + (b.y - a.y) * u;
          ctx.beginPath();
          ctx.arc(x, y, 1.6, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(92,225,255,${0.35 + intensity * 0.45})`;
          ctx.fill();
        }
      }

      for (const n of nodes) {
        const beat = 0.5 + 0.5 * Math.sin(t * 2.4 + n.phase);
        const r = n.r + (active ? beat * (1 + intensity) : beat * 0.3);
        ctx.beginPath();
        ctx.arc(n.x, n.y, r + 4, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(79,124,255,${active ? 0.12 + intensity * 0.15 : 0.04})`;
        ctx.fill();
        ctx.beginPath();
        ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
        ctx.fillStyle = active
          ? `rgba(${n.layer === 2 ? "92,225,255" : "167,139,250"},${0.55 + beat * 0.35})`
          : "rgba(140,160,210,0.45)";
        ctx.fill();
      }

      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
    };
  }, [active, intensity]);

  return <canvas ref={canvasRef} className={`neural-net ${className}`.trim()} aria-hidden />;
}
