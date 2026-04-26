import clsx from "clsx";
import { useStore, type IssueFilter } from "../lib/store";
import type { Region } from "../lib/types";
import { Select } from "./Select";

const REGIONS: { id: Region | "all"; label: string }[] = [
  { id: "all", label: "All regions" },
  { id: "IRQ_BAGHDAD", label: "Baghdad, Iraq" },
  { id: "IRQ_MOSUL", label: "Mosul, Iraq" },
  { id: "SYR_ALEPPO", label: "Aleppo, Syria" },
  { id: "SYR_DAMASCUS", label: "Damascus, Syria" },
  { id: "YEM_SANAA", label: "Sana'a, Yemen" },
  { id: "LBN_BEIRUT", label: "Beirut, Lebanon" },
];

const ISSUES: { id: IssueFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "missing_person", label: "Missing person" },
  { id: "medical", label: "Medical" },
  { id: "resource_shortage", label: "Resource" },
  { id: "safety", label: "Safety" },
];

export function FilterBar() {
  const region = useStore((s) => s.selectedRegion);
  const issue = useStore((s) => s.issueFilter);
  const setRegion = useStore((s) => s.selectRegion);
  const setIssue = useStore((s) => s.setIssueFilter);

  return (
    <div className="border-b border-surface-300 bg-white px-6 py-3 flex items-center gap-5 flex-wrap">
      <div className="flex items-center gap-2.5">
        <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">
          /// Region
        </span>
        <Select<Region | "all">
          value={region}
          onChange={(v) => setRegion(v)}
          options={REGIONS.map((r) => ({ value: r.id, label: r.label }))}
          ariaLabel="Filter by region"
        />
      </div>

      <span className="h-4 w-px bg-surface-300" />

      <div className="flex items-center gap-2.5 flex-wrap">
        <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">
          /// Issue
        </span>
        <div className="flex items-center border border-surface-300 rounded-sm overflow-hidden">
          {ISSUES.map((it) => {
            const active = issue === it.id;
            return (
              <button
                key={it.id}
                onClick={() => setIssue(it.id)}
                className={clsx(
                  "px-3 py-1 text-[12.5px] font-medium transition border-r border-surface-300 last:border-r-0",
                  active
                    ? "bg-ink-900 text-white"
                    : "bg-white text-ink-600 hover:text-ink-900 hover:bg-surface-100",
                )}
              >
                {it.label}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
