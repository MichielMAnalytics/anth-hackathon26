import { useStore } from "../../lib/store";
import { navigate } from "../../lib/router";
import type { DashboardRegion, DashboardTheme } from "../../lib/types";
import { Sparkline } from "../Sparkline";
import { UrgencyMeter } from "./UrgencyMeter";

const NEED_LABEL: Record<string, string> = {
  missing_person: "person",
  water: "water",
  food: "food",
  insulin: "med",
  medicine: "med",
  medical: "med",
  shelter: "shelter",
  "baby formula": "formula",
  "adult escort": "escort",
};

interface Props {
  region: DashboardRegion;
  index: number;
  onAct: (theme: DashboardTheme, region: DashboardRegion) => void;
}

export function RegionCard({ region, index, onAct }: Props) {
  const setRegion = useStore((s) => s.selectRegion);
  const indexLabel = `[${String(index + 1).padStart(2, "0")}]`;

  return (
    <div className="group relative bg-white border border-surface-300 rounded-lg overflow-hidden transition hover:border-ink-400/40">
      <div className="px-6 sm:px-7 pt-5 pb-4">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">
              <span>///</span>
              <span>Region</span>
              {region.anomaly && (
                <>
                  <span className="text-surface-400">·</span>
                  <span className="text-sev-high">↑ unusual volume</span>
                </>
              )}
            </div>
            <h3 className="font-display text-[28px] leading-[1.05] font-semibold text-ink-900 tracking-tighter mt-2">
              {region.label}
            </h3>
            <div className="mt-2.5 text-[12.5px] text-ink-500 flex items-center gap-2 flex-wrap">
              <span>
                <span className="font-mono text-ink-900">{region.openCases}</span>{" "}
                open
              </span>
              <span className="text-surface-400">·</span>
              <span>
                <span className="font-mono text-ink-900">{region.distinctSenders}</span>{" "}
                reporters
              </span>
              <span className="text-surface-400">·</span>
              <span>
                <span className="font-mono text-ink-900">{region.msgsPerMin.toFixed(1)}</span>{" "}
                msg/min
              </span>
            </div>
          </div>
          <div className="shrink-0 font-mono text-[11px] tracking-[0.1em] text-ink-400 tabular-nums pt-1">
            {indexLabel}
          </div>
        </div>

        <div className="mt-4 flex items-center justify-between gap-4">
          <UrgencyMeter value={region.urgency} />
        </div>

        {region.sparkline.some((v) => v > 0) && (
          <div className="mt-3 -mx-1 opacity-80">
            <Sparkline data={region.sparkline} width={680} height={26} />
          </div>
        )}
      </div>

      {region.themes.length === 0 ? (
        <div className="px-6 sm:px-7 py-4 border-t border-surface-300 text-[12.5px] text-ink-500">
          No clear themes yet — channel monitored.
        </div>
      ) : (
        <ul className="border-t border-surface-300 divide-y divide-surface-300">
          {region.themes.map((t) => (
            <li
              key={t.need}
              className="px-6 sm:px-7 py-4 flex items-start gap-4 hover:bg-surface-100 transition"
            >
              <div className="shrink-0 mt-0.5 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-400 w-[60px]">
                {NEED_LABEL[t.need] ?? "signal"}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <div className="text-[14px] font-semibold text-ink-900 tracking-tight">
                    {t.label}
                  </div>
                  {t.distressCount > 0 && (
                    <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-sev-critical">
                      · {t.distressCount} distress
                    </span>
                  )}
                </div>
                <div className="text-[12.5px] text-ink-500 mt-0.5 leading-snug">
                  <span className="font-mono text-ink-700">{t.count}</span> report{t.count === 1 ? "" : "s"}
                  {t.distinctSenders > 0 && (
                    <>
                      {" from "}
                      <span className="font-mono text-ink-700">{t.distinctSenders}</span> sender
                      {t.distinctSenders === 1 ? "" : "s"}
                    </>
                  )}
                  {t.locations.length > 0 && (
                    <>
                      {" near "}
                      <span className="text-ink-700">{t.locations.slice(0, 2).join(", ")}</span>
                      {t.locations.length > 2 && " …"}
                    </>
                  )}
                </div>
              </div>
              <button
                onClick={() => onAct(t, region)}
                className="shrink-0 px-3 py-1.5 font-mono text-[10.5px] uppercase tracking-[0.12em] font-semibold bg-brand-600 hover:bg-brand-700 text-white rounded-sm whitespace-nowrap transition"
              >
                {t.action}
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="px-6 sm:px-7 py-3 border-t border-surface-300 flex items-center justify-between font-mono text-[10.5px] uppercase tracking-[0.14em]">
        <button
          onClick={() => {
            setRegion(region.region);
            navigate("cases");
          }}
          className="text-ink-500 hover:text-ink-900 transition"
        >
          View cases <span aria-hidden>→</span>
        </button>
        <button
          onClick={() => {
            setRegion(region.region);
            navigate("map");
          }}
          className="text-ink-500 hover:text-ink-900 transition"
        >
          Show on map <span aria-hidden>→</span>
        </button>
      </div>
    </div>
  );
}
