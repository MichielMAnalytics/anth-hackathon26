import { useMemo } from "react";
import clsx from "clsx";
import { useStore, SEV_RANK, type IssueFilter } from "../lib/store";
import type { Category, Region } from "../lib/types";
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

interface Props {
  region: Region | "all";
  issue: IssueFilter;
}

export function IncidentList({ region, issue }: Props) {
  const incidents = useStore((s) => s.incidents);
  const selectedId = useStore((s) => s.selectedIncidentId);
  const select = useStore((s) => s.selectIncident);

  const me = useStore((s) => s.me);
  const sorted = useMemo(() => {
    const allowed =
      me && me.role === "junior" && me.regions.length > 0
        ? new Set(me.regions)
        : null;
    const list = Object.values(incidents).filter((i) => {
      if (allowed && !allowed.has(i.region)) return false;
      if (region !== "all" && i.region !== region) return false;
      if (issue !== "all" && i.category !== issue) return false;
      return true;
    });
    list.sort((a, b) => {
      const r = SEV_RANK[a.severity] - SEV_RANK[b.severity];
      if (r !== 0) return r;
      const ta = a.lastActivity ? new Date(a.lastActivity).getTime() : 0;
      const tb = b.lastActivity ? new Date(b.lastActivity).getTime() : 0;
      return tb - ta;
    });
    return list;
  }, [incidents, region, issue, me]);

  return (
    <div className="h-full flex flex-col">
      <div className="px-5 py-4 border-b border-surface-300 bg-surface-50">
        <div className="text-meta uppercase tracking-wider text-ink-500">
          Cases
        </div>
        <div className="font-display text-xl font-semibold text-ink-900 mt-0.5">
          {sorted.length}{" "}
          <span className="text-ink-500 font-normal">open</span>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto">
        {sorted.length === 0 && (
          <div className="p-6 text-sm text-ink-500">
            No cases match the current filter. Adjust region or issue type.
          </div>
        )}
        {sorted.map((inc) => {
          const active = inc.id === selectedId;
          const closed = inc.details?.status === "closed";
          return (
            <button
              key={inc.id}
              onClick={() => select(inc.id)}
              className={clsx(
                "w-full text-left px-5 py-3 border-b border-surface-200 transition relative",
                active
                  ? "bg-brand-50/50 border-l-[3px] border-l-brand-600 pl-[17px]"
                  : "hover:bg-surface-100 bg-surface-50",
              )}
            >
              <div className="flex items-start gap-3">
                <div className="text-base leading-none mt-1 text-ink-700">
                  {ICONS[inc.category] ?? "•"}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <SeverityChip severity={inc.severity} />
                    {closed && (
                      <span className="text-meta uppercase tracking-wider px-1.5 py-0.5 rounded border border-surface-300 bg-surface-100 text-ink-500">
                        closed
                      </span>
                    )}
                    <div className="text-meta font-mono text-ink-500 ml-auto">
                      {timeAgo(inc.lastActivity)}
                    </div>
                  </div>
                  <div
                    className={clsx(
                      "mt-1.5 text-sm font-semibold leading-snug",
                      closed
                        ? "text-ink-500 line-through"
                        : "text-ink-900",
                    )}
                  >
                    {inc.title}
                  </div>
                  <div className="mt-0.5 text-meta text-ink-500">
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
