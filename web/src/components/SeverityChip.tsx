import clsx from "clsx";
import type { Severity } from "../lib/types";

const STYLES: Record<Severity, string> = {
  critical: "bg-sev-critical/15 text-sev-critical border-sev-critical/40",
  high: "bg-sev-high/15 text-sev-high border-sev-high/40",
  medium: "bg-sev-medium/15 text-sev-medium border-sev-medium/40",
  low: "bg-sev-low/15 text-sev-low border-sev-low/40",
};

const LABEL: Record<Severity, string> = {
  critical: "CRIT",
  high: "HIGH",
  medium: "MED",
  low: "LOW",
};

export function SeverityChip({ severity }: { severity: Severity }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center px-1.5 py-0.5 text-[10px] font-mono font-medium border rounded",
        STYLES[severity],
      )}
    >
      {LABEL[severity]}
    </span>
  );
}
