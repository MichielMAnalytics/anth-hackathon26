import clsx from "clsx";
import type { Severity } from "../lib/types";

const STYLES: Record<Severity, string> = {
  critical: "bg-sev-critical/10 text-sev-critical border-sev-critical/30",
  high: "bg-sev-high/10 text-sev-high border-sev-high/30",
  medium: "bg-sev-medium/10 text-sev-medium border-sev-medium/30",
  low: "bg-sev-low/10 text-sev-low border-sev-low/30",
};

const LABEL: Record<Severity, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
};

export function SeverityChip({ severity }: { severity: Severity }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center px-2 py-0.5 text-meta font-medium border rounded-full",
        STYLES[severity],
      )}
    >
      {LABEL[severity]}
    </span>
  );
}
