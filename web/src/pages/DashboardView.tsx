import { useEffect, useMemo, useState } from "react";
import { fetchDashboard } from "../lib/api";
import { useStore } from "../lib/store";
import type {
  Audience,
  Channel,
  Dashboard,
  DashboardRegion,
  DashboardTheme,
  Incident,
  Region,
  SendMode,
} from "../lib/types";
import { RegionCard } from "../components/dashboard/RegionCard";
import { RecentDistress } from "../components/dashboard/RecentDistress";
import { SendModal } from "../components/send/SendModal";

interface PreparedSend {
  mode: SendMode;
  incident: Incident;
  defaults: {
    audienceId?: string;
    body?: string;
    channel?: Channel;
    region?: Region;
  };
}

function suggestAudienceFor(
  theme: DashboardTheme,
  region: DashboardRegion,
  audiences: Audience[],
): string | undefined {
  if (theme.suggestedAudienceId) {
    const exists = audiences.find((a) => a.id === theme.suggestedAudienceId);
    if (exists) return exists.id;
  }
  if (theme.need === "missing_person") {
    const civ = audiences.find(
      (a) =>
        a.regions.includes(region.region) && a.roles.includes("civilian"),
    );
    if (civ) return civ.id;
  }
  return audiences.find((a) => a.regions.includes(region.region))?.id;
}

function buildBody(theme: DashboardTheme, region: DashboardRegion): string {
  if (theme.need === "missing_person") {
    return `AMBER ALERT — please watch for a missing child reported in ${region.label}. If you have any information, reply to this number.`;
  }
  const loc = theme.locations[0] ? ` near ${theme.locations[0]}` : "";
  return `War Child here. We have ${theme.count} reports of ${theme.label.toLowerCase()}${loc} in ${region.label}. If you can help (deliver, coordinate, or confirm status), reply to this number.`;
}

export function DashboardView() {
  const audiences = useStore((s) => s.audiences);
  const incidents = useStore((s) => s.incidents);
  const me = useStore((s) => s.me);

  const [data, setData] = useState<Dashboard | null>(null);
  const [send, setSend] = useState<PreparedSend | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = () =>
      fetchDashboard()
        .then((d) => !cancelled && setData(d))
        .catch(() => {});
    load();
    const id = setInterval(load, 8000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const visibleRegions = useMemo(() => {
    if (!data) return [];
    if (me && me.role === "junior" && me.regions.length > 0) {
      const allowed = new Set(me.regions);
      return data.regions.filter((r) => allowed.has(r.region));
    }
    return data.regions;
  }, [data, me]);

  const summary = useMemo(() => {
    if (visibleRegions.length === 0) return null;
    return visibleRegions.reduce(
      (acc, r) => {
        acc.cases += r.openCases;
        acc.distress += r.distressCount;
        acc.msgs += r.messageCount;
        if (r.anomaly) acc.anomalies += 1;
        return acc;
      },
      { cases: 0, distress: 0, msgs: 0, anomalies: 0 },
    );
  }, [visibleRegions]);

  function handleAct(theme: DashboardTheme, region: DashboardRegion) {
    const incidentId =
      theme.incidentIds?.[0] ??
      Object.values(incidents).find((i) => i.region === region.region)?.id;
    const incident = incidentId ? incidents[incidentId] : null;
    if (!incident) return;
    const audienceId = suggestAudienceFor(theme, region, audiences);
    setSend({
      mode: theme.need === "missing_person" ? "alert" : "request",
      incident,
      defaults: {
        audienceId,
        region: region.region,
        channel: "fallback",
        body: buildBody(theme, region),
      },
    });
  }

  return (
    <div className="h-full overflow-y-auto md:overflow-hidden md:grid md:grid-cols-[1fr_400px] min-h-0 bg-surface-100">
      <main className="px-4 sm:px-10 py-8 sm:py-12 md:overflow-y-auto">
        <div className="max-w-3xl lg:max-w-6xl mx-auto space-y-10">
          {/* Editorial header */}
          <header className="grid grid-cols-1 lg:grid-cols-[1fr_auto] items-end gap-6">
            <div>
              <div className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-500">
                /// Insights
              </div>
              <h1 className="font-display text-[40px] sm:text-[52px] leading-[1] font-semibold text-ink-900 tracking-tightest mt-3">
                Where to act first.
              </h1>
              <p className="text-[14px] text-ink-500 mt-3 max-w-[58ch] leading-relaxed">
                Regions ranked by urgency. Each card surfaces patterns across
                recent civilian messages — and the broadcast we think will
                help.
              </p>
            </div>
            {data && (
              <div className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-500 lg:text-right">
                <div>Window</div>
                <div className="text-ink-900 normal-case tracking-normal mt-1 text-[13px]">
                  last {data.windowMinutes} min
                </div>
              </div>
            )}
          </header>

          {/* Summary banner — flat, no boxes, vertical rules */}
          {summary && (
            <div className="grid grid-cols-3 border-y border-surface-300">
              <Stat label="Open cases" value={summary.cases} />
              <Stat
                label="Distress flags"
                value={summary.distress}
                tone="critical"
                divider
              />
              <Stat
                label="Active anomalies"
                value={summary.anomalies}
                tone="high"
                divider
              />
            </div>
          )}

          {!data && (
            <div className="border border-dashed border-surface-300 rounded-lg p-10 text-center">
              <div className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-400">
                Loading
              </div>
              <div className="font-display text-[18px] text-ink-700 tracking-tight mt-1.5">
                Reading the wire…
              </div>
            </div>
          )}

          {data && visibleRegions.length === 0 && (
            <div className="border border-dashed border-surface-300 rounded-lg p-10 text-center">
              <div className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-400">
                No scope
              </div>
              <div className="text-[13px] text-ink-500 mt-1.5 max-w-[42ch] mx-auto">
                No regions in your scope right now. Switch operator from the
                header to widen the view.
              </div>
            </div>
          )}

          {visibleRegions.length > 0 && (
            <section>
              <div className="flex items-baseline justify-between mb-4 pb-3 border-b border-surface-300">
                <div className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-500">
                  /// Regions
                </div>
                <div className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-400 tabular-nums">
                  {String(visibleRegions.length).padStart(2, "0")} total
                </div>
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 items-start">
                {visibleRegions.map((r, i) => (
                  <div
                    key={r.region}
                    className="stagger-item"
                    style={{ ["--stagger-delay" as never]: `${i * 50}ms` }}
                  >
                    <RegionCard region={r} index={i} onAct={handleAct} />
                  </div>
                ))}
              </div>
            </section>
          )}

          <footer className="pt-6 border-t border-surface-300 flex items-center justify-between font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-400">
            <span>SafeThread · Operator Console</span>
            <span className="normal-case tracking-normal">
              {visibleRegions.length} region{visibleRegions.length === 1 ? "" : "s"} · live
            </span>
          </footer>
        </div>
      </main>

      <aside className="md:border-l border-t md:border-t-0 border-surface-300 bg-white md:overflow-y-auto md:max-h-full">
        <div className="px-6 py-8 sm:py-10 space-y-5">
          <div>
            <div className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-500">
              /// The wire
            </div>
            <h2 className="font-display text-[22px] leading-tight font-semibold text-ink-900 tracking-tighter mt-2">
              Recent distress
            </h2>
            <p className="text-[12.5px] text-ink-500 mt-1.5 leading-snug">
              Latest civilian messages flagged distress. Click to open the case.
            </p>
          </div>
          <RecentDistress items={data?.recentDistress ?? []} />
        </div>
      </aside>

      {send && (
        <SendModal
          mode={send.mode}
          incident={send.incident}
          audiences={audiences}
          defaults={send.defaults}
          onClose={() => setSend(null)}
        />
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
  divider,
}: {
  label: string;
  value: number;
  tone?: "critical" | "high";
  divider?: boolean;
}) {
  const color =
    tone === "critical"
      ? "text-sev-critical"
      : tone === "high"
        ? "text-sev-high"
        : "text-ink-900";
  return (
    <div className={`px-6 py-5 ${divider ? "border-l border-surface-300" : ""}`}>
      <div className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-500">
        {label}
      </div>
      <div
        className={`font-display text-[44px] sm:text-[52px] leading-none tracking-tightest mt-2 tabular-nums ${color}`}
      >
        {value}
      </div>
    </div>
  );
}
