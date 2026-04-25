import { useMemo } from "react";
import clsx from "clsx";
import { useStore, SEV_RANK } from "../lib/store";
import type { Category } from "../lib/types";
import { SeverityChip } from "./SeverityChip";

const ICONS: Record<Category, string> = {
  missing_person: "👤",
  resource_shortage: "💧",
  medical: "⚕",
  safety: "⚠",
  other: "•",
};

function timeAgo(iso: string | null): string {
  if (!iso) return "—";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return `${Math.round(s)}s`;
  if (s < 3600) return `${Math.round(s / 60)}m`;
  if (s < 86400) return `${Math.round(s / 3600)}h`;
  return `${Math.round(s / 86400)}d`;
}

export function IncidentList({
  filterRegion,
}: {
  filterRegion?: string | null;
}) {
  const incidents = useStore((s) => s.incidents);
  const selectedId = useStore((s) => s.selectedIncidentId);
  const select = useStore((s) => s.selectIncident);

  const sorted = useMemo(() => {
    const list = Object.values(incidents).filter(
      (i) => !filterRegion || i.region === filterRegion,
    );
    list.sort((a, b) => {
      const r = SEV_RANK[a.severity] - SEV_RANK[b.severity];
      if (r !== 0) return r;
      const ta = a.lastActivity ? new Date(a.lastActivity).getTime() : 0;
      const tb = b.lastActivity ? new Date(b.lastActivity).getTime() : 0;
      return tb - ta;
    });
    return list;
  }, [incidents, filterRegion]);

  return (
    <div className="h-full flex flex-col">
      <div className="px-5 py-4 border-b border-paper-200 bg-paper-50">
        <div className="text-meta uppercase tracking-wider text-paper-500">
          Incidents
        </div>
        <div className="font-display text-lg text-paper-900 mt-0.5">
          {sorted.length} active
          {filterRegion && (
            <span className="text-meta font-mono uppercase tracking-wider text-paper-500 ml-2">
              · {filterRegion}
            </span>
          )}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto">
        {sorted.length === 0 && (
          <div className="p-6 text-sm text-paper-600">
            No incidents in this view.
          </div>
        )}
        {sorted.map((inc) => {
          const active = inc.id === selectedId;
          return (
            <button
              key={inc.id}
              onClick={() => select(inc.id)}
              className={clsx(
                "w-full text-left px-5 py-3 border-b border-paper-200 transition",
                active ? "bg-accent-50" : "hover:bg-paper-100 bg-paper-50",
              )}
            >
              <div className="flex items-start gap-3">
                <div className="text-base leading-none mt-0.5 text-paper-700">
                  {ICONS[inc.category] ?? "•"}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <SeverityChip severity={inc.severity} />
                    <div className="text-meta font-mono text-paper-500 ml-auto">
                      {timeAgo(inc.lastActivity)}
                    </div>
                  </div>
                  <div className="mt-1.5 text-sm font-medium text-paper-900 leading-snug">
                    {inc.title}
                  </div>
                  <div className="mt-0.5 text-meta text-paper-500">
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
