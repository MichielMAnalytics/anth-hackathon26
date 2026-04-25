import { useMemo, useState } from "react";
import type { RegionTimeline } from "../lib/types";

interface Props {
  data: RegionTimeline | null;
  height?: number;
}

const PADDING = { top: 14, right: 8, bottom: 24, left: 30 };

export function TimelineChart({ data, height = 140 }: Props) {
  const [width, setWidth] = useState(320);
  const [hover, setHover] = useState<number | null>(null);

  const chart = useMemo(() => {
    if (!data || data.buckets.length === 0) return null;
    const buckets = data.buckets;
    const max = Math.max(2, ...buckets.map((b) => b.count));
    const innerW = width - PADDING.left - PADDING.right;
    const innerH = height - PADDING.top - PADDING.bottom;
    const stepX = innerW / Math.max(1, buckets.length - 1);

    const x = (i: number) => PADDING.left + i * stepX;
    const y = (v: number) =>
      PADDING.top + innerH - (v / max) * innerH;

    const linePath = buckets
      .map((b, i) => `${i === 0 ? "M" : "L"} ${x(i).toFixed(1)} ${y(b.count).toFixed(1)}`)
      .join(" ");

    const areaPath =
      linePath +
      ` L ${x(buckets.length - 1).toFixed(1)} ${(PADDING.top + innerH).toFixed(1)}` +
      ` L ${x(0).toFixed(1)} ${(PADDING.top + innerH).toFixed(1)} Z`;

    // grid lines (3 horizontal)
    const grid = [0, 0.5, 1].map((f) => ({
      y: PADDING.top + innerH - f * innerH,
      label: Math.round(f * max).toString(),
    }));

    // x-axis labels: first, middle, last (HH:MM)
    const fmt = (iso: string) => {
      const d = new Date(iso);
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    };
    const xLabels = [
      { x: x(0), label: fmt(buckets[0].ts) },
      {
        x: x(Math.floor(buckets.length / 2)),
        label: fmt(buckets[Math.floor(buckets.length / 2)].ts),
      },
      { x: x(buckets.length - 1), label: fmt(buckets[buckets.length - 1].ts) },
    ];

    return { buckets, max, x, y, linePath, areaPath, grid, xLabels, innerW, innerH };
  }, [data, width, height]);

  if (!data || !chart) {
    return (
      <div
        ref={(el) => {
          if (el) {
            const w = el.getBoundingClientRect().width;
            if (w !== width) setWidth(w);
          }
        }}
        style={{ height }}
        className="w-full rounded-md border border-dashed border-surface-300 bg-surface-50 flex items-center justify-center text-meta text-ink-500"
      >
        No data
      </div>
    );
  }

  const fmt = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };
  const hovered = hover !== null ? chart.buckets[hover] : null;

  return (
    <div
      ref={(el) => {
        if (el) {
          const w = el.getBoundingClientRect().width;
          if (Math.abs(w - width) > 1) setWidth(w);
        }
      }}
      className="w-full relative"
      style={{ height }}
    >
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        onMouseLeave={() => setHover(null)}
        onMouseMove={(e) => {
          const rect = (e.target as SVGElement).closest("svg")!.getBoundingClientRect();
          const x = e.clientX - rect.left - PADDING.left;
          const stepX = chart.innerW / Math.max(1, chart.buckets.length - 1);
          const i = Math.round(x / stepX);
          if (i >= 0 && i < chart.buckets.length) setHover(i);
          else setHover(null);
        }}
      >
        {/* grid */}
        {chart.grid.map((g, i) => (
          <g key={i}>
            <line
              x1={PADDING.left}
              x2={width - PADDING.right}
              y1={g.y}
              y2={g.y}
              stroke="#e2e8f0"
              strokeDasharray={i === 2 ? "0" : "2 3"}
            />
            <text
              x={PADDING.left - 6}
              y={g.y + 3}
              textAnchor="end"
              fill="#94a3b8"
              fontSize="10"
              fontFamily="JetBrains Mono"
            >
              {g.label}
            </text>
          </g>
        ))}

        {/* area + line */}
        <path d={chart.areaPath} fill="rgba(230, 46, 46, 0.10)" />
        <path
          d={chart.linePath}
          fill="none"
          stroke="#e62e2e"
          strokeWidth="1.75"
          strokeLinejoin="round"
          strokeLinecap="round"
        />

        {/* x-axis labels */}
        {chart.xLabels.map((l, i) => (
          <text
            key={i}
            x={l.x}
            y={height - 6}
            textAnchor={i === 0 ? "start" : i === 2 ? "end" : "middle"}
            fill="#94a3b8"
            fontSize="10"
            fontFamily="JetBrains Mono"
          >
            {l.label}
          </text>
        ))}

        {/* hover marker */}
        {hover !== null && (
          <>
            <line
              x1={chart.x(hover)}
              x2={chart.x(hover)}
              y1={PADDING.top}
              y2={PADDING.top + chart.innerH}
              stroke="#cbd5e1"
              strokeDasharray="2 2"
            />
            <circle
              cx={chart.x(hover)}
              cy={chart.y(chart.buckets[hover].count)}
              r="3.5"
              fill="#e62e2e"
              stroke="#fff"
              strokeWidth="1.5"
            />
          </>
        )}
      </svg>

      {hovered && (
        <div
          className="absolute pointer-events-none rounded border border-surface-300 bg-white shadow-soft px-2 py-1 text-meta"
          style={{
            left: Math.min(
              width - 110,
              Math.max(0, chart.x(hover!) - 50),
            ),
            top: Math.max(0, chart.y(hovered.count) - 36),
          }}
        >
          <div className="font-mono text-ink-900">
            {hovered.count} {hovered.count === 1 ? "msg" : "msgs"}
          </div>
          <div className="text-ink-500">{fmt(hovered.ts)}</div>
        </div>
      )}
    </div>
  );
}
