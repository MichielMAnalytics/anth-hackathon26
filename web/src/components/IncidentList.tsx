import { useMemo } from "react";
import clsx from "clsx";
import { useStore } from "../lib/store";
import type { Category, Severity } from "../lib/types";
import { SeverityChip } from "./SeverityChip";

const ICONS: Record<Category, string> = {
  missing_person: "👤",
  resource_shortage: "💧",
  medical: "⚕",
  safety: "⚠",
  other: "•",
};

const SEV_RANK: Record<Severity, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

function timeAgo(iso: string | null): string {
  if (!iso) return "—";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return `${Math.round(s)}s`;
  if (s < 3600) return `${Math.round(s / 60)}m`;
  if (s < 86400) return `${Math.round(s / 3600)}h`;
  return `${Math.round(s / 86400)}d`;
}

export function IncidentList() {
  const incidents = useStore((s) => s.incidents);
  const selectedId = useStore((s) => s.selectedId);
  const select = useStore((s) => s.select);
  const sorted = useMemo(() => {
    const list = Object.values(incidents);
    list.sort((a, b) => {
      const r = SEV_RANK[a.severity] - SEV_RANK[b.severity];
      if (r !== 0) return r;
      const ta = a.lastActivity ? new Date(a.lastActivity).getTime() : 0;
      const tb = b.lastActivity ? new Date(b.lastActivity).getTime() : 0;
      return tb - ta;
    });
    return list;
  }, [incidents]);

  return (
    <div className="h-full flex flex-col">
      <div className="px-4 py-3 border-b border-ink-800 flex items-center justify-between">
        <div>
          <div className="text-xs uppercase tracking-wider text-ink-400">
            Incidents
          </div>
          <div className="text-sm text-ink-200">
            {sorted.length} active
          </div>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto">
        {sorted.length === 0 && (
          <div className="p-6 text-sm text-ink-400">
            No incidents yet. Click <span className="font-mono text-ink-200">Seed demo</span> in
            the header to load sample data.
          </div>
        )}
        {sorted.map((inc) => {
          const active = inc.id === selectedId;
          return (
            <button
              key={inc.id}
              onClick={() => select(inc.id)}
              className={clsx(
                "w-full text-left px-4 py-3 border-b border-ink-800/60 transition",
                active
                  ? "bg-ink-800"
                  : "hover:bg-ink-900/60",
              )}
            >
              <div className="flex items-start gap-2">
                <div className="text-lg leading-none mt-0.5">
                  {ICONS[inc.category] ?? "•"}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <SeverityChip severity={inc.severity} />
                    <div className="text-[11px] text-ink-400 font-mono">
                      {timeAgo(inc.lastActivity)}
                    </div>
                  </div>
                  <div className="mt-1 text-sm font-medium text-ink-100 truncate">
                    {inc.title}
                  </div>
                  <div className="mt-0.5 text-xs text-ink-400">
                    {inc.messageCount} message
                    {inc.messageCount === 1 ? "" : "s"}
                  </div>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
