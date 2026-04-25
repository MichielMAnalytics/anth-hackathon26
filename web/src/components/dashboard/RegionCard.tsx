import { useStore } from "../../lib/store";
import type { DashboardRegion, DashboardTheme } from "../../lib/types";
import { Sparkline } from "../Sparkline";
import { UrgencyMeter } from "./UrgencyMeter";

const NEED_ICON: Record<string, string> = {
  missing_person: "👤",
  water: "💧",
  food: "🍞",
  insulin: "⚕",
  medicine: "⚕",
  medical: "⚕",
  shelter: "🏠",
  "baby formula": "🍼",
  "adult escort": "🤝",
};

interface Props {
  region: DashboardRegion;
  onAct: (theme: DashboardTheme, region: DashboardRegion) => void;
}

export function RegionCard({ region, onAct }: Props) {
  const setRegion = useStore((s) => s.selectRegion);
  const setTab = useStore((s) => s.setTab);

  return (
    <div className="bg-white border border-surface-300 rounded-lg shadow-soft overflow-hidden">
      <div className="px-5 py-4 border-b border-surface-200">
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 sm:gap-4">
          <div className="min-w-0 flex-1">
            <div className="text-meta uppercase tracking-wider text-ink-500">
              Region
            </div>
            <div className="font-display text-xl font-semibold text-ink-900 mt-0.5">
              {region.label}
            </div>
            <div className="mt-1.5 text-meta text-ink-500 flex items-center gap-3 whitespace-nowrap overflow-hidden">
              <span className="font-mono">
                {region.openCases} open case{region.openCases === 1 ? "" : "s"}
              </span>
              <span>·</span>
              <span className="font-mono">
                {region.distinctSenders} reporters
              </span>
              <span>·</span>
              <span className="truncate">
                <span className="font-mono">{region.msgsPerMin.toFixed(1)}</span>{" "}
                msgs/min
                {region.baselineMsgsPerMin > 0 && (
                  <>
                    {" "}
                    <span className="text-ink-400">
                      (base {region.baselineMsgsPerMin.toFixed(1)})
                    </span>
                  </>
                )}
              </span>
            </div>
          </div>
          <div className="shrink-0 flex flex-row sm:flex-col items-center sm:items-end gap-2 flex-wrap">
            <UrgencyMeter value={region.urgency} />
            {region.anomaly && (
              <span className="text-meta uppercase tracking-wider text-sev-high border border-sev-high/30 bg-sev-high/5 px-2 py-0.5 rounded-full">
                ↑ unusual volume
              </span>
            )}
          </div>
        </div>
        {region.sparkline.some((v) => v > 0) && (
          <div className="mt-3">
            <Sparkline data={region.sparkline} width={680} height={32} />
          </div>
        )}
      </div>

      {region.themes.length === 0 ? (
        <div className="px-5 py-4 text-sm text-ink-500">
          No clear themes yet — monitor for incoming reports.
        </div>
      ) : (
        <ul className="divide-y divide-surface-200">
          {region.themes.map((t) => (
            <li
              key={t.need}
              className="px-5 py-3.5 flex items-start gap-3 hover:bg-surface-50/60"
            >
              <div className="text-xl leading-none mt-0.5 select-none">
                {NEED_ICON[t.need] ?? "•"}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <div className="text-sm font-semibold text-ink-900">
                    {t.label}
                  </div>
                  {t.distressCount > 0 && (
                    <span className="text-meta uppercase tracking-wider text-sev-critical border border-sev-critical/30 bg-sev-critical/5 px-1.5 py-px rounded">
                      {t.distressCount} distress
                    </span>
                  )}
                </div>
                <div className="text-xs text-ink-600 mt-0.5 leading-snug">
                  {t.count} report{t.count === 1 ? "" : "s"}
                  {t.distinctSenders > 0 && (
                    <>
                      {" from "}
                      <span className="font-mono text-ink-700">
                        {t.distinctSenders}
                      </span>{" "}
                      sender{t.distinctSenders === 1 ? "" : "s"}
                    </>
                  )}
                  {t.locations.length > 0 && (
                    <>
                      {" near "}
                      <span className="text-ink-700">
                        {t.locations.slice(0, 2).join(", ")}
                      </span>
                      {t.locations.length > 2 && " …"}
                    </>
                  )}
                </div>
              </div>
              <button
                onClick={() => onAct(t, region)}
                className="shrink-0 px-3 py-1.5 text-sm font-semibold bg-brand-600 hover:bg-brand-700 text-white rounded-md whitespace-nowrap"
              >
                {t.action}
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="px-5 py-3 border-t border-surface-200 bg-surface-50 flex items-center justify-between">
        <button
          onClick={() => {
            setRegion(region.region);
            setTab("cases");
          }}
          className="text-meta uppercase tracking-wider text-ink-600 hover:text-ink-900"
        >
          View all cases →
        </button>
        <button
          onClick={() => {
            setRegion(region.region);
            setTab("map");
          }}
          className="text-meta uppercase tracking-wider text-ink-600 hover:text-ink-900"
        >
          Show on map →
        </button>
      </div>
    </div>
  );
}
