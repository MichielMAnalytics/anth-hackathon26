import { describeAnomaly } from "../lib/anomaly";
import type { RegionStats } from "../lib/types";

export function AnomalyBanner({ stats }: { stats: RegionStats }) {
  if (!stats.anomaly) return null;
  return (
    <div className="flex items-start gap-3 px-4 py-3 rounded-lg border border-sev-high/30 bg-sev-high/5">
      <div className="text-sev-high text-lg leading-none mt-0.5">⤴</div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-sev-high">
          Unusual volume in {stats.label}
        </div>
        <div className="text-xs text-ink-700 mt-0.5">
          {describeAnomaly(stats)} Something may be developing — consider a
          broadcast.
        </div>
      </div>
    </div>
  );
}
