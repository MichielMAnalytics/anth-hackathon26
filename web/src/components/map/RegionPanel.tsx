import { useEffect, useMemo, useState } from "react";
import { fetchRegionTimeline } from "../../lib/api";
import { useStore } from "../../lib/store";
import { navigate } from "../../lib/router";
import type { RegionTimeline } from "../../lib/types";
import { AnomalyBanner } from "../AnomalyBanner";
import { SeverityChip } from "../SeverityChip";
import { TimelineChart } from "../TimelineChart";

const fmt = new Intl.NumberFormat("en-US");

export function RegionPanel() {
  const selectedRegion = useStore((s) => s.selectedRegion);
  const regions = useStore((s) => s.regions);
  const incidents = useStore((s) => s.incidents);
  const selectIncident = useStore((s) => s.selectIncident);

  const stats =
    selectedRegion && selectedRegion !== "all" ? regions[selectedRegion] : null;

  const [timeline, setTimeline] = useState<RegionTimeline | null>(null);

  useEffect(() => {
    if (!stats) {
      setTimeline(null);
      return;
    }
    let cancelled = false;
    const load = () =>
      fetchRegionTimeline(stats.region, 60, 60)
        .then((t) => !cancelled && setTimeline(t))
        .catch(() => {});
    load();
    const id = setInterval(load, 8000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [stats?.region]);

  const inRegion = useMemo(() => {
    if (!selectedRegion || selectedRegion === "all") return [];
    return Object.values(incidents)
      .filter((i) => i.region === selectedRegion)
      .sort(
        (a, b) =>
          (b.lastActivity ? new Date(b.lastActivity).getTime() : 0) -
          (a.lastActivity ? new Date(a.lastActivity).getTime() : 0),
      );
  }, [selectedRegion, incidents]);

  if (!stats) {
    return (
      <div className="p-8 text-center">
        <div className="font-display text-lg font-semibold text-ink-900">
          Select a region
        </div>
        <div className="mt-2 text-sm text-ink-600">
          Click a marker on the map, or pick a region from the filter bar at
          the top, to see live message volume and stats.
        </div>
      </div>
    );
  }

  return (
    <div className="p-5 space-y-5">
      <div>
        <div className="text-meta uppercase tracking-wider text-ink-500">
          Region
        </div>
        <div className="font-display text-2xl font-semibold text-ink-900 mt-0.5 tracking-tight">
          {stats.label}
        </div>
      </div>

      <AnomalyBanner stats={stats} />

      <section className="space-y-2">
        <div className="flex items-baseline justify-between">
          <div className="text-meta uppercase tracking-wider text-ink-500">
            Messages — last 60 min
          </div>
          <div className="font-mono text-sm text-ink-900">
            {timeline ? `${timeline.total} total` : "—"}
          </div>
        </div>
        <TimelineChart data={timeline} height={140} />
        <div className="flex items-center justify-between text-meta text-ink-500">
          <span>
            now: <span className="font-mono text-ink-900">{stats.msgsPerMin.toFixed(1)}</span>{" "}
            msgs/min
          </span>
          <span>
            baseline:{" "}
            <span className="font-mono">
              {stats.baselineMsgsPerMin.toFixed(1)}
            </span>
          </span>
        </div>
      </section>

      <div className="grid grid-cols-2 gap-3">
        <Stat label="Reachable" value={fmt.format(stats.reachable)} />
        <Stat
          label="Active cases"
          value={String(stats.incidentCount)}
        />
      </div>

      {inRegion.length > 0 && (
        <div>
          <div className="text-meta uppercase tracking-wider text-ink-500 mb-2">
            Cases in this region
          </div>
          <ul className="space-y-1.5">
            {inRegion.slice(0, 6).map((inc) => (
              <li key={inc.id}>
                <button
                  onClick={() => {
                    selectIncident(inc.id);
                    navigate("cases");
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

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-surface-300 bg-white px-3 py-2.5">
      <div className="text-meta uppercase tracking-wider text-ink-500">
        {label}
      </div>
      <div className="font-mono text-lg text-ink-900 mt-0.5 leading-tight">
        {value}
      </div>
    </div>
  );
}
