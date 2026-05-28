import { useMemo, useState, type PointerEvent, type WheelEvent } from "react";
import clsx from "clsx";

import type { CorrelationEdge, CorrelationNode } from "../types";

interface PositionedNode extends CorrelationNode {
  x: number;
  y: number;
  category: string;
}

const nodeStyles: Record<string, string> = {
  domain: "fill-cyan-400",
  ip: "fill-emerald-400",
  url: "fill-violet-400",
  service: "fill-amber-400",
  technology: "fill-orange-400",
  finding: "fill-rose-400",
  evidence: "fill-slate-300",
  relationship: "fill-raven-muted",
  report: "fill-blue-300",
  knowledge: "fill-teal-300",
};

export function CorrelationNetwork({
  nodes,
  edges,
}: {
  nodes: CorrelationNode[];
  edges: CorrelationEdge[];
}): JSX.Element {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [scale, setScale] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null);
  const layout = useMemo(() => positionNodes(nodes), [nodes]);
  const nodeById = useMemo(
    () => new Map(layout.map((node) => [node.id, node])),
    [layout],
  );
  const selectedNode = selectedNodeId ? nodeById.get(selectedNodeId) : null;
  const selectedEdge = selectedEdgeId
    ? edges.find((edge) => edge.id === selectedEdgeId)
    : null;

  function handleWheel(event: WheelEvent<SVGSVGElement>): void {
    event.preventDefault();
    setScale((current) => {
      const next = event.deltaY > 0 ? current - 0.08 : current + 0.08;
      return Math.min(1.8, Math.max(0.55, Number(next.toFixed(2))));
    });
  }

  function handlePointerDown(event: PointerEvent<SVGSVGElement>): void {
    setDragStart({ x: event.clientX - offset.x, y: event.clientY - offset.y });
  }

  function handlePointerMove(event: PointerEvent<SVGSVGElement>): void {
    if (!dragStart) {
      return;
    }
    setOffset({
      x: event.clientX - dragStart.x,
      y: event.clientY - dragStart.y,
    });
  }

  return (
    <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-4">
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-lg font-semibold">Network View</h2>
          <p className="mt-1 text-sm text-raven-muted">
            Drag to pan, scroll to zoom, click nodes or relationships for context.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            setScale(1);
            setOffset({ x: 0, y: 0 });
            setSelectedNodeId(null);
            setSelectedEdgeId(null);
          }}
          className="rounded-md border border-raven-border px-3 py-2 text-sm text-raven-muted hover:text-raven-text"
        >
          Reset view
        </button>
      </div>

      <svg
        viewBox="0 0 900 460"
        className="mt-4 h-[460px] w-full rounded-md border border-raven-border bg-raven-bg"
        role="img"
        aria-label="Investigation correlation network"
        onWheel={handleWheel}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={() => setDragStart(null)}
        onPointerLeave={() => setDragStart(null)}
      >
        <g transform={`translate(${offset.x} ${offset.y}) scale(${scale})`}>
          {edges.map((edge) => {
            const source = nodeById.get(edge.source_node_id);
            const target = nodeById.get(edge.target_node_id);
            if (!source || !target) {
              return null;
            }
            const isSelected = selectedEdgeId === edge.id;
            return (
              <g key={edge.id}>
                <line
                  x1={source.x}
                  y1={source.y}
                  x2={target.x}
                  y2={target.y}
                  className={clsx(
                    "stroke-raven-border",
                    isSelected && "stroke-raven-cyan",
                  )}
                  strokeWidth={isSelected ? 3 : 1.5}
                />
                <line
                  x1={source.x}
                  y1={source.y}
                  x2={target.x}
                  y2={target.y}
                  className="cursor-pointer stroke-transparent"
                  strokeWidth={14}
                  onClick={(event) => {
                    event.stopPropagation();
                    setSelectedNodeId(null);
                    setSelectedEdgeId(edge.id);
                  }}
                />
              </g>
            );
          })}

          {layout.map((node) => {
            const isSelected = selectedNodeId === node.id;
            return (
              <g
                key={node.id}
                transform={`translate(${node.x} ${node.y})`}
                className="cursor-pointer"
                onClick={(event) => {
                  event.stopPropagation();
                  setSelectedEdgeId(null);
                  setSelectedNodeId(node.id);
                }}
              >
                <circle
                  r={isSelected ? 22 : 17}
                  className={clsx(nodeStyles[node.category] ?? nodeStyles.relationship)}
                  opacity={isSelected ? 1 : 0.86}
                />
                <circle
                  r={isSelected ? 25 : 20}
                  className="fill-transparent stroke-raven-border"
                  strokeWidth={isSelected ? 2 : 1}
                />
                <text
                  y={34}
                  textAnchor="middle"
                  className="fill-raven-text text-[11px]"
                >
                  {shortLabel(node.label)}
                </text>
              </g>
            );
          })}
        </g>
      </svg>

      <div className="mt-4 grid gap-4 lg:grid-cols-[0.6fr_0.4fr]">
        <Legend nodes={layout} />
        <SelectionPanel
          node={selectedNode ?? null}
          edge={selectedEdge ?? null}
          nodeById={nodeById}
        />
      </div>
    </section>
  );
}

function Legend({ nodes }: { nodes: PositionedNode[] }): JSX.Element {
  const categories = Array.from(new Set(nodes.map((node) => node.category))).sort();
  return (
    <div className="rounded-md border border-raven-border bg-raven-panelSoft p-3">
      <p className="text-xs uppercase tracking-wide text-raven-muted">Categories</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {categories.map((category) => (
          <span
            key={category}
            className="inline-flex items-center gap-2 rounded border border-raven-border px-2 py-1 text-xs text-raven-muted"
          >
            <span
              className={clsx(
                "h-2.5 w-2.5 rounded-full",
                nodeStyles[category] ?? nodeStyles.relationship,
              )}
            />
            {category}
          </span>
        ))}
      </div>
    </div>
  );
}

function SelectionPanel({
  node,
  edge,
  nodeById,
}: {
  node: PositionedNode | null;
  edge: CorrelationEdge | null;
  nodeById: Map<string, PositionedNode>;
}): JSX.Element {
  if (edge) {
    const source = nodeById.get(edge.source_node_id);
    const target = nodeById.get(edge.target_node_id);
    return (
      <div className="rounded-md border border-raven-border bg-raven-panelSoft p-3">
        <p className="text-xs uppercase tracking-wide text-raven-muted">
          Selected Relationship
        </p>
        <h3 className="mt-2 font-semibold">{edge.correlation_type}</h3>
        <p className="mt-2 text-sm text-raven-muted">{edge.summary}</p>
        <p className="mt-3 text-xs text-raven-muted">
          {source?.label ?? edge.source_node_id} to {target?.label ?? edge.target_node_id}
        </p>
      </div>
    );
  }
  if (node) {
    return (
      <div className="rounded-md border border-raven-border bg-raven-panelSoft p-3">
        <p className="text-xs uppercase tracking-wide text-raven-muted">
          Selected Node
        </p>
        <h3 className="mt-2 font-semibold">{node.label}</h3>
        <p className="mt-2 text-sm text-raven-muted">
          {node.category} from {node.source}
        </p>
      </div>
    );
  }
  return (
    <div className="rounded-md border border-raven-border bg-raven-panelSoft p-3 text-sm text-raven-muted">
      Select a node or relationship to inspect its context.
    </div>
  );
}

function positionNodes(nodes: CorrelationNode[]): PositionedNode[] {
  const width = 780;
  const height = 340;
  const centerX = 450;
  const centerY = 220;
  const radiusX = width / 2;
  const radiusY = height / 2;
  const total = Math.max(nodes.length, 1);
  return nodes.map((node, index) => {
    const angle = (Math.PI * 2 * index) / total - Math.PI / 2;
    return {
      ...node,
      category: nodeCategory(node),
      x: centerX + Math.cos(angle) * radiusX,
      y: centerY + Math.sin(angle) * radiusY,
    };
  });
}

function nodeCategory(node: CorrelationNode): string {
  const entityType = String(node.metadata.entity_type ?? "").toLowerCase();
  if (entityType.includes("domain")) {
    return "domain";
  }
  if (entityType.includes("ip")) {
    return "ip";
  }
  if (entityType.includes("url")) {
    return "url";
  }
  if (entityType.includes("service")) {
    return "service";
  }
  if (entityType.includes("technology")) {
    return "technology";
  }
  if (node.node_type === "finding") {
    return "finding";
  }
  if (node.node_type === "knowledge_citation") {
    return "knowledge";
  }
  if (node.node_type === "report") {
    return "report";
  }
  if (node.node_type === "threat_provider") {
    return "evidence";
  }
  return "relationship";
}

function shortLabel(label: string): string {
  return label.length > 18 ? `${label.slice(0, 15)}...` : label;
}
