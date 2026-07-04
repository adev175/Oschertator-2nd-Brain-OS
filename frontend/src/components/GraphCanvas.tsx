import React, { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import type { GraphNode, GraphEdge, GraphData } from '../types';

interface GraphCanvasProps {
  data: GraphData;
  onNodeClick: (noteId: string, notePath?: string) => void;
}

/* Accent-based 6-color ramp */
const COLOR_RAMP = [
  '#c8f04b',
  '#a8d840',
  '#88c035',
  '#6ba82c',
  '#509022',
  '#3a7818',
];

/* Simple hash to map folder strings to stable index 0-5 */
function folderColor(folder: string): string {
  let h = 0;
  for (let i = 0; i < folder.length; i++) {
    h = ((h << 5) - h + folder.charCodeAt(i)) | 0;
  }
  const idx = Math.abs(h) % COLOR_RAMP.length;
  return COLOR_RAMP[idx];
}

/* Simple seeded pseudo-random number generator */
function seededRandom(seed: number): () => number {
  let s = seed | 0;
  return () => {
    s = (s * 1664525 + 1013904223) | 0;
    return ((s >>> 0) / 4294967296);
  };
}

const GraphCanvas: React.FC<GraphCanvasProps> = ({ data, onNodeClick }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const simRef = useRef({
    nodes: [] as GraphNode[],
    edges: [] as GraphEdge[],
    alpha: 1,
    running: false,
    hoveredNode: null as GraphNode | null,
    neighborSet: new Set<string>(),
    camera: { x: 0, y: 0, zoom: 1 } as CameraState,
    dragging: false,
    dragNode: null as GraphNode | null,
    dragStart: { x: 0, y: 0 },
    mouse: { x: 0, y: 0 },
    lastFrame: 0,
    rafId: 0,
  });

  /* Filter state */
  const [folderFilter, setFolderFilter] = useState('');
  const [tagFilter, setTagFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [tooltip, setTooltip] = useState<{ x: number; y: number; title: string } | null>(null);

  /* Derive unique folders from initial data for filter dropdown */
  const folders = useMemo(() => {
    const set = new Set<string>();
    data.nodes.forEach((n) => {
      const parts = n.folder.split('/');
      if (parts.length > 1) set.add(parts[parts.length - 2]);
    });
    return Array.from(set);
  }, [data]);

  /* Initialize simulation when data changes */
  const initSimulation = useCallback(() => {
    const s = simRef.current;
    const nodeMap = new Map<string, GraphNode>();

    data.nodes.forEach((n, i) => {
      const rng = seededRandom(i * 31 + 7);
      nodeMap.set(n.id, {
        ...n,
        x: (rng() - 0.5) * 600,
        y: (rng() - 0.5) * 400,
        vx: 0,
        vy: 0,
      });
    });

    s.nodes = Array.from(nodeMap.values());
    s.edges = [...data.edges];
    s.alpha = 1;
  }, [data]);

  /* Filtered nodes */
  const filteredNodes = useMemo(() => {
    return simRef.current.nodes.filter((n) => {
      if (folderFilter && !n.folder.includes(folderFilter)) return false;
      if (tagFilter && !(n.tags?.includes(tagFilter) || false)) return false;
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        if (!n.title.toLowerCase().includes(q) && !n.id.toLowerCase().includes(q)) return false;
      }
      return true;
    });
  }, [simRef.current.nodes, folderFilter, tagFilter, searchQuery]);

  /* Filtered edges (both endpoints must be in filtered nodes) */
  const filteredEdgeSet = useMemo(() => {
    const ids = new Set(filteredNodes.map((n) => n.id));
    return simRef.current.edges.filter((e) => ids.has(e.source) && ids.has(e.target));
  }, [filteredNodes, simRef.current.edges]);

  /* Build adjacency for neighbor highlighting */
  const adjacency = useMemo(() => {
    const adj = new Map<string, Set<string>>();
    filteredEdgeSet.forEach((e) => {
      if (!adj.has(e.source)) adj.set(e.source, new Set());
      if (!adj.has(e.target)) adj.set(e.target, new Set());
      adj.get(e.source)!.add(e.target);
      adj.get(e.target)!.add(e.source);
    });
    return adj;
  }, [filteredEdgeSet]);

  /* Re-init when filters change or data changes */
  useEffect(() => {
    initSimulation();
  }, [initSimulation, folderFilter, tagFilter, searchQuery]);

  /* Main simulation + render loop */
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const s = simRef.current;

    /* Size canvas */
    const resize = () => {
      const container = containerRef.current;
      if (!container) return;
      const dpr = window.devicePixelRatio || 1;
      canvas.width = container.clientWidth * dpr;
      canvas.height = container.clientHeight * dpr;
      ctx.scale(dpr, dpr);
      canvas.style.width = `${container.clientWidth}px`;
      canvas.style.height = `${container.clientHeight}px`;
    };
    resize();
    window.addEventListener('resize', resize);

    let frameId = 0;

    const tick = (time: number) => {
      const dt = Math.min((time - s.lastFrame) / 16.667, 3);
      s.lastFrame = time;
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;

      /* --- Simulation step --- */
      const nodes = s.nodes;

      if (s.alpha > 0.001) {
        const REPULSION = 1200;
        const SPRING_K = 0.02;
        const SPRING_REST = 60;
        const GRAVITY = 0.005;
        const DAMPING = 0.6;

        /* n^2 repulsion among filtered nodes */
        const active = filteredNodes;
        const activeSet = new Set(active.map((n) => n.id));
        const activeMap = new Map<string, GraphNode>();
        active.forEach((n) => activeMap.set(n.id, n));

        for (let i = 0; i < active.length; i++) {
          const a = active[i];
          let fx = 0;
          let fy = 0;
          for (let j = i + 1; j < active.length; j++) {
            const b = active[j];
            let dx = b.x - a.x;
            let dy = b.y - a.y;
            let dist2 = dx * dx + dy * dy;
            if (dist2 < 1) { dx = (Math.random() - 0.5) * 2; dy = (Math.random() - 0.5) * 2; dist2 = 4; }
            let force = REPULSION / dist2;
            let dxn = dx / Math.sqrt(dist2);
            let dyn = dy / Math.sqrt(dist2);
            fx -= force * dxn;
            fy -= force * dyn;
          }
          /* Gravity toward center */
          fx -= a.x * GRAVITY;
          fy -= a.y * GRAVITY;

          if (a !== s.dragNode) {
            a.vx = (a.vx + fx * s.alpha * dt) * DAMPING;
            a.vy = (a.vy + fy * s.alpha * dt) * DAMPING;
          }
        }

        /* Spring forces along edges */
        filteredEdgeSet.forEach((e) => {
          const src = activeMap.get(e.source);
          const tgt = activeMap.get(e.target);
          if (!src || !tgt) return;
          const dx = tgt.x - src.x;
          const dy = tgt.y - src.y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          const force = (dist - SPRING_REST) * SPRING_K * s.alpha * dt;
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;
          if (src !== s.dragNode) { src.vx += fx; src.vy += fy; }
          if (tgt !== s.dragNode) { tgt.vx -= fx; tgt.vy -= fy; }
        });

        /* Update positions */
        active.forEach((n) => {
          if (n === s.dragNode) return;
          n.x += n.vx * dt;
          n.y += n.vy * dt;
        });

        /* Cool down */
        s.alpha *= 0.995;
        if (s.alpha < 0.001) s.alpha = 0;
      }

      /* --- Render --- */
      const c = s.camera;
      ctx.clearRect(0, 0, w, h);

      /* Perspective grid floor */
      ctx.save();
      const cx = w / 2 + c.x;
      const cy = h / 2 + c.y;
      const gridSpacing = 40 * c.zoom;
      const fov = 400 * c.zoom;

      /* Draw grid lines converging toward center */
      ctx.strokeStyle = 'rgba(28, 35, 28, 0.5)';
      ctx.lineWidth = 0.5;
      for (let i = -15; i <= 15; i++) {
        ctx.beginPath();
        /* Horizontal lines with perspective */
        const baseY = cy + i * gridSpacing;
        ctx.moveTo(cx - fov, baseY - Math.abs(i) * 2 * c.zoom);
        ctx.lineTo(cx + fov, baseY - Math.abs(i) * 2 * c.zoom);
        ctx.stroke();
      }
      for (let i = -15; i <= 15; i++) {
        ctx.beginPath();
        /* Vertical lines with perspective convergence */
        const baseX = cx + i * gridSpacing;
        ctx.moveTo(baseX - Math.abs(i) * 1.5 * c.zoom, cy - fov);
        ctx.lineTo(baseX, cy + fov);
        ctx.stroke();
      }
      ctx.restore();

      /* Transform for camera */
      ctx.save();
      ctx.translate(cx, cy);
      ctx.scale(c.zoom, c.zoom);

      /* Draw edges */
      filteredEdgeSet.forEach((e) => {
        const src = s.nodes.find((n) => n.id === e.source);
        const tgt = s.nodes.find((n) => n.id === e.target);
        if (!src || !tgt) return;

        const isNeighbor = s.hoveredNode && s.neighborSet.has(e.source) && s.neighborSet.has(e.target);
        const dimmed = s.hoveredNode && !isNeighbor;

        ctx.strokeStyle = dimmed ? 'rgba(28, 35, 28, 0.15)' : 'rgba(28, 35, 28, 0.6)';
        ctx.lineWidth = isNeighbor ? 1.5 : 1;
        ctx.beginPath();
        ctx.moveTo(src.x, src.y);
        ctx.lineTo(tgt.x, tgt.y);
        ctx.stroke();
      });

      /* Draw nodes */
      const displayed = filteredNodes;
      displayed.forEach((n) => {
        const hasPos = n.x !== undefined && n.y !== undefined;
        if (!hasPos) return;

        const degree = n.inDegree + n.outDegree;
        const radius = Math.max(3, Math.min(10, Math.sqrt(degree)));
        const color = folderColor(n.folder);

        const isHovered = s.hoveredNode === n;
        const isNeighbor = s.neighborSet.has(n.id);
        const isHighlighted = isHovered || isNeighbor;
        const dimmed = s.hoveredNode && !isHighlighted;

        ctx.globalAlpha = dimmed ? 0.25 : (isHighlighted ? 1 : 0.7);

        /* Glow for highlighted */
        if (isHighlighted) {
          ctx.shadowColor = color;
          ctx.shadowBlur = isHovered ? 12 : 6;
        } else {
          ctx.shadowColor = 'transparent';
          ctx.shadowBlur = 0;
        }

        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(n.x, n.y, radius, 0, Math.PI * 2);
        ctx.fill();

        ctx.shadowColor = 'transparent';
        ctx.shadowBlur = 0;
        ctx.globalAlpha = 1;
      });

      ctx.restore();

      frameId = requestAnimationFrame(tick);
    };

    frameId = requestAnimationFrame(tick);

    return () => {
      window.removeEventListener('resize', resize);
      cancelAnimationFrame(frameId);
    };
  }, [filteredNodes, filteredEdgeSet, adjacency]);

  /* --- Interaction handlers --- */
  interface CameraState {
    x: number;
    y: number;
    zoom: number;
  }

  const screenToWorld = useCallback((sx: number, sy: number, c: CameraState) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const cx = canvas.clientWidth / 2 + c.x;
    const cy = canvas.clientHeight / 2 + c.y;
    return {
      x: (sx - cx) / c.zoom,
      y: (sy - cy) / c.zoom,
    };
  }, []);

  const findNodeAt = useCallback((wx: number, wy: number): GraphNode | null => {
    const s = simRef.current;
    for (let i = s.nodes.length - 1; i >= 0; i--) {
      const n = s.nodes[i];
      if (n.x === undefined || n.y === undefined) continue;
      const degree = n.inDegree + n.outDegree;
      const r = Math.max(3, Math.min(10, Math.sqrt(degree))) + 4;
      const dx = wx - n.x;
      const dy = wy - n.y;
      if (dx * dx + dy * dy < r * r) return n;
    }
    return null;
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    const s = simRef.current;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const sx = e.clientX - rect.left;
    const sy = e.clientY - rect.top;
    const world = screenToWorld(sx, sy, s.camera);
    const node = findNodeAt(world.x, world.y);

    if (node) {
      s.dragging = true;
      s.dragNode = node;
      node.vx = 0;
      node.vy = 0;
    } else {
      s.dragging = true;
      s.dragNode = null;
      s.dragStart = { x: e.clientX - s.camera.x, y: e.clientY - s.camera.y };
    }
  }, [screenToWorld, findNodeAt]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    const s = simRef.current;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const sx = e.clientX - rect.left;
    const sy = e.clientY - rect.top;
    const world = screenToWorld(sx, sy, s.camera);

    s.mouse = { x: sx, y: sy };

    if (s.dragging) {
      if (s.dragNode) {
        s.dragNode.x = world.x;
        s.dragNode.y = world.y;
        s.alpha = Math.max(s.alpha, 0.1);
      } else {
        s.camera.x = e.clientX - s.dragStart.x;
        s.camera.y = e.clientY - s.dragStart.y;
      }
      return;
    }

    /* Hover detection */
    const node = findNodeAt(world.x, world.y);
    s.hoveredNode = node;

    /* Update neighbor set */
    s.neighborSet.clear();
    if (node) {
      s.neighborSet.add(node.id);
      const neighbors = adjacency.get(node.id);
      if (neighbors) neighbors.forEach((nid) => s.neighborSet.add(nid));

      /* Show tooltip */
      setTooltip({
        x: sx + 12,
        y: sy - 12,
        title: node.title,
      });
    } else {
      setTooltip(null);
    }
  }, [screenToWorld, findNodeAt, adjacency]);

  const handleMouseUp = useCallback((_e: React.MouseEvent) => {
    const s = simRef.current;
    if (s.dragNode && !wasPanning(s)) {
      /* Node was clicked, not dragged far - open preview */
      onNodeClick(s.dragNode.id, s.dragNode.folder);
    }
    s.dragging = false;
    s.dragNode = null;
  }, [onNodeClick]);

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const s = simRef.current;
    const factor = e.deltaY > 0 ? 0.9 : 1.1;
    s.camera.zoom = Math.max(0.2, Math.min(5, s.camera.zoom * factor));
  }, []);

  /* Track if mouse moved significantly during drag (pan vs click) */
  let dragDist = 0;
  const origHandleMouseDown = handleMouseDown;
  const wasPanning = (s: typeof simRef.current): boolean => {
    return dragDist > 3;
  };

  /* Override to track drag distance */
  const handleMouseDownWithDist = useCallback((e: React.MouseEvent) => {
    dragDist = 0;
    const start = { x: e.clientX, y: e.clientY };
    const onMove = (ev: MouseEvent) => {
      dragDist += Math.hypot(ev.clientX - start.x, ev.clientY - start.y);
    };
    const onUp = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    origHandleMouseDown(e);
  }, [origHandleMouseDown]);

  return (
    <div ref={containerRef} style={{ width: '100%', height: '100%', position: 'relative' }}>
      {/* Graph Controls */}
      <div className="graph-controls">
        <input
          className="graph-control-input"
          type="text"
          placeholder="Search nodes..."
          value={searchQuery}
          onChange={(e) => { dragDist = 0; setSearchQuery(e.target.value); }}
        />
        <select
          className="graph-control-input"
          value={folderFilter}
          onChange={(e) => { dragDist = 0; setFolderFilter(e.target.value); }}
        >
          <option value="">All folders</option>
          {folders.map((f) => (
            <option key={f} value={f}>{f}</option>
          ))}
        </select>
        <input
          className="graph-control-input"
          type="text"
          placeholder="Filter by tag..."
          value={tagFilter}
          onChange={(e) => { dragDist = 0; setTagFilter(e.target.value); }}
        />
        <div className="graph-count" style={{ cursor: 'default' }}>
          Shown {filteredNodes.length} / total {data.nodes.length}
        </div>
      </div>

      <canvas
        ref={canvasRef}
        className="graph-canvas"
        onMouseDown={handleMouseDownWithDist}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={() => {
          simRef.current.hoveredNode = null;
          simRef.current.neighborSet.clear();
          setTooltip(null);
        }}
        onWheel={handleWheel}
      />

      {/* Tooltip */}
      {tooltip && (
        <div
          className="graph-tooltip"
          style={{ left: tooltip.x, top: tooltip.y }}
        >
          {tooltip.title}
        </div>
      )}
    </div>
  );
};

export default GraphCanvas;
