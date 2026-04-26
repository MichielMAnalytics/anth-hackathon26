import { useMemo } from "react";
import clsx from "clsx";
import { useStore, SEV_RANK, type IssueFilter } from "../lib/store";
import type { Category, Region, Severity } from "../lib/types";
import { SeverityChip } from "./SeverityChip";

const CATEGORY_LABEL: Record<Category, string> = {
  missing_person: "person",
  resource_shortage: "resource",
  medical: "med",
  safety: "safety",
  other: "signal",
};

const SEV_RAIL: Record<Severity, string> = {
  critical: "bg-sev-critical",
  high: "bg-sev-high",
  medium: "bg-sev-medium",
  low: "bg-sev-low",
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
    <div className="h-full flex flex-col bg-white">
      <div className="px-5 py-5 border-b border-surface-300">
        <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">
          /// Cases
        </div>
        <div className="font-display text-[28px] leading-none font-semibold text-ink-900 tracking-tighter mt-2 tabular-nums">
          {String(sorted.length).padStart(2, "0")}
          <span className="ml-2 text-[14px] font-normal text-ink-500 tracking-tight">
            open
          </span>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto">
        {sorted.length === 0 && (
          <div className="p-6 text-[13px] text-ink-500 leading-snug">
            No cases match the current filter. Adjust region or issue type.
          </div>
        )}
        {sorted.map((inc, i) => {
          const active = inc.id === selectedId;
          return (
            <button
              key={inc.id}
              onClick={() => select(inc.id)}
              className={clsx(
                "group relative w-full text-left px-5 py-4 border-b border-surface-300 transition",
                active
                  ? "bg-surface-100"
                  : "bg-white hover:bg-surface-100/60",
              )}
            >
              <span
                className={clsx(
                  "absolute left-0 top-0 bottom-0 w-[2px] transition-opacity",
                  active ? SEV_RAIL[inc.severity] : "opacity-0",
                )}
              />
              <div className="flex items-center gap-3 mb-1.5">
                <span className="font-mono text-[10px] tracking-[0.1em] text-ink-400 tabular-nums">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <SeverityChip severity={inc.severity} />
                <span className="ml-auto font-mono text-[10px] uppercase tracking-[0.14em] text-ink-400">
                  {timeAgo(inc.lastActivity)}
                </span>
              </div>
              <div className="font-display text-[14.5px] font-semibold text-ink-900 tracking-tight leading-snug pl-[26px]">
                {inc.title}
              </div>
              <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500 mt-1 pl-[26px]">
                {CATEGORY_LABEL[inc.category] ?? "signal"}
                <span className="text-surface-400"> · </span>
                <span className="text-ink-700">{inc.messageCount}</span>{" "}
                msg{inc.messageCount === 1 ? "" : "s"}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
