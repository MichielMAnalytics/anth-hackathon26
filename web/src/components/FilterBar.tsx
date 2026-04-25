import clsx from "clsx";
import { useStore, type IssueFilter } from "../lib/store";
import type { Region } from "../lib/types";

const REGIONS: { id: Region | "all"; label: string }[] = [
  { id: "all", label: "All regions" },
  { id: "IRQ_BAGHDAD", label: "Baghdad, Iraq" },
  { id: "IRQ_MOSUL", label: "Mosul, Iraq" },
  { id: "SYR_ALEPPO", label: "Aleppo, Syria" },
  { id: "SYR_DAMASCUS", label: "Damascus, Syria" },
  { id: "YEM_SANAA", label: "Sana'a, Yemen" },
  { id: "LBN_BEIRUT", label: "Beirut, Lebanon" },
];

const ISSUES: { id: IssueFilter; label: string; icon: string }[] = [
  { id: "all", label: "All issues", icon: "◇" },
  { id: "missing_person", label: "Missing person", icon: "👤" },
  { id: "medical", label: "Medical", icon: "⚕" },
  { id: "resource_shortage", label: "Resource shortage", icon: "💧" },
  { id: "safety", label: "Safety", icon: "⚠" },
];

export function FilterBar() {
  const region = useStore((s) => s.selectedRegion);
  const issue = useStore((s) => s.issueFilter);
  const setRegion = useStore((s) => s.selectRegion);
  const setIssue = useStore((s) => s.setIssueFilter);

  return (
    <div className="border-b border-surface-300 bg-surface-50 px-6 py-3 flex items-center gap-4 flex-wrap">
      <label className="flex items-center gap-2">
        <span className="text-meta uppercase tracking-wider text-ink-500">
          Region
        </span>
        <select
          value={region}
          onChange={(e) =>
            setRegion(e.target.value as Region | "all")
          }
          className="bg-surface-50 border border-surface-300 rounded-md px-2.5 py-1.5 text-sm text-ink-900 focus:outline-none focus:border-brand-600 focus:ring-1 focus:ring-brand-600/20"
        >
          {REGIONS.map((r) => (
            <option key={r.id} value={r.id}>
              {r.label}
            </option>
          ))}
        </select>
      </label>

      <div className="h-5 w-px bg-surface-300" />

      <div className="flex items-center gap-1.5 flex-wrap">
        <span className="text-meta uppercase tracking-wider text-ink-500 mr-1">
          Issue
        </span>
        {ISSUES.map((it) => {
          const active = issue === it.id;
          return (
            <button
              key={it.id}
              onClick={() => setIssue(it.id)}
              className={clsx(
                "inline-flex items-center gap-1.5 px-2.5 py-1 text-sm rounded-full border transition",
                active
                  ? "bg-brand-600 border-brand-600 text-white"
                  : "bg-surface-50 border-surface-300 text-ink-700 hover:bg-surface-100",
              )}
            >
              <span className="text-[12px]">{it.icon}</span>
              <span>{it.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
