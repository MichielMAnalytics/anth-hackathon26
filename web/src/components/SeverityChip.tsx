import clsx from "clsx";
import type { Severity } from "../lib/types";

const STYLES: Record<Severity, string> = {
  critical: "text-sev-critical",
  high: "text-sev-high",
  medium: "text-sev-medium",
  low: "text-sev-low",
};

const DOT: Record<Severity, string> = {
  critical: "bg-sev-critical",
  high: "bg-sev-high",
  medium: "bg-sev-medium",
  low: "bg-sev-low",
};

const LABEL: Record<Severity, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
};

export function SeverityChip({ severity }: { severity: Severity }) {
  return (
    <span className="inline-flex items-center gap-1.5 select-none">
      <span className={clsx("w-1.5 h-1.5 rounded-full", DOT[severity])} />
      <span
        className={clsx(
          "font-mono text-[10px] uppercase tracking-[0.14em] font-semibold",
          STYLES[severity],
        )}
      >
        {LABEL[severity]}
      </span>
    </span>
  );
}
