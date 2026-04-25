import { useMemo } from "react";
import { useStore } from "../../lib/store";
import { AnomalyBanner } from "../AnomalyBanner";
import { Sparkline } from "../Sparkline";
import { SeverityChip } from "../SeverityChip";

const fmt = new Intl.NumberFormat("en-US");

export function RegionPanel() {
  const selectedRegion = useStore((s) => s.selectedRegion);
  const regions = useStore((s) => s.regions);
  const incidents = useStore((s) => s.incidents);
  const setTab = useStore((s) => s.setTab);
  const selectIncident = useStore((s) => s.selectIncident);

  const stats =
    selectedRegion && selectedRegion !== "all" ? regions[selectedRegion] : null;

  const inRegion = useMemo(() => {
    if (!selectedRegion) return [];
    return Object.values(incidents)
      .filter((i) => i.region === selectedRegion)
      .sort(
        (a, b) =>
          (b.lastActivity ? new Date(b.lastActivity).getTime() : 0) -
          (a.lastActivity ? new Date(a.lastActivity).getTime() : 0),
      );
  }, [selectedRegion, incidents]);

  // synthetic 30-min sparkline using current msgs/min as latest sample
  const spark = useMemo(() => {
    if (!stats) return [];
    const latest = stats.msgsPerMin;
    const base = stats.baselineMsgsPerMin;
    return Array.from({ length: 30 }, (_, i) => {
      const noise = (Math.sin(i * 0.7) + 1) * 0.5;
      return i < 27 ? base * (0.6 + noise * 0.8) : latest * (0.7 + i * 0.05);
    });
  }, [stats]);

  if (!stats) {
    return (
      <div className="p-8 text-center">
        <div className="font-display text-lg text-ink-700">
          Select a region
        </div>
        <div className="mt-2 text-sm text-ink-600">
          Click a marker on the map to see reach, message volume, and any
          anomalies.
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-5">
      <div>
        <div className="text-meta uppercase tracking-wider text-ink-500">
          Region
        </div>
        <div className="font-display text-2xl font-semibold text-ink-900 mt-0.5">
          {stats.label}
        </div>
      </div>

      <AnomalyBanner stats={stats} />

      <div className="grid grid-cols-2 gap-4">
        <Stat label="Reachable" value={fmt.format(stats.reachable)} />
        <Stat label="Active incidents" value={String(stats.incidentCount)} />
        <Stat label="Messages" value={fmt.format(stats.messageCount)} />
        <Stat
          label="Msgs / min"
          value={stats.msgsPerMin.toFixed(1)}
          hint={`baseline ${stats.baselineMsgsPerMin.toFixed(1)}`}
        />
      </div>

      <div>
        <div className="text-meta uppercase tracking-wider text-ink-500 mb-2">
          Last 30 minutes
        </div>
        <Sparkline data={spark} width={280} height={48} />
      </div>

      {inRegion.length > 0 && (
        <div>
          <div className="text-meta uppercase tracking-wider text-ink-500 mb-2">
            Incidents in this region
          </div>
          <ul className="space-y-1.5">
            {inRegion.slice(0, 5).map((inc) => (
              <li key={inc.id}>
                <button
                  onClick={() => {
                    selectIncident(inc.id);
                    setTab("cases");
                  }}
                  className="w-full text-left px-3 py-2 rounded-md border border-surface-300 bg-white hover:bg-surface-100 transition flex items-center gap-2"
                >
                  <SeverityChip severity={inc.severity} />
                  <span className="text-sm text-ink-900 truncate">
                    {inc.title}
                  </span>
                  <span className="ml-auto text-meta text-ink-500 font-mono">
                    {inc.messageCount} msg
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="rounded-lg border border-surface-300 bg-white px-3 py-2.5">
      <div className="text-meta uppercase tracking-wider text-ink-500">
        {label}
      </div>
      <div className="font-mono text-lg text-ink-900 mt-0.5 leading-tight">
        {value}
      </div>
      {hint && (
        <div className="text-meta text-ink-500 mt-0.5">{hint}</div>
      )}
    </div>
  );
}
