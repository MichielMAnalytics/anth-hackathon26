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
  // generic fallback: any audience that includes this region
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
    // pick an incident to anchor the send to (used for incident-id linkage in
    // the send payload). Prefer one in the same region; else fall back to any.
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
    <div className="h-full grid grid-cols-[1fr_360px] min-h-0 bg-surface-100">
      <main className="overflow-y-auto px-6 py-6">
        <div className="max-w-3xl mx-auto space-y-4">
          <header className="flex items-end justify-between gap-4">
            <div>
              <div className="text-meta uppercase tracking-wider text-ink-500">
                Insights
              </div>
              <h1 className="font-display text-2xl font-bold text-ink-900 tracking-tight mt-0.5">
                Where to act first
              </h1>
              <p className="text-sm text-ink-600 mt-1 max-w-prose">
                Regions ranked by urgency. Each card surfaces the patterns
                across recent civilian messages and a one-click broadcast we
                think will help.
              </p>
            </div>
            {summary && (
              <div className="flex items-center gap-4 text-meta">
                <Stat label="Cases" value={summary.cases} />
                <Stat label="Distress" value={summary.distress} tone="critical" />
                <Stat label="Anomalies" value={summary.anomalies} tone="high" />
              </div>
            )}
          </header>

          {!data && (
            <div className="rounded-lg border border-dashed border-surface-300 bg-white p-8 text-center text-sm text-ink-500">
              Loading insights…
            </div>
          )}

          {data && visibleRegions.length === 0 && (
            <div className="rounded-lg border border-dashed border-surface-300 bg-white p-8 text-center text-sm text-ink-500">
              No regions in your scope right now. Switch to a different
              operator from the header to widen the view.
            </div>
          )}

          {visibleRegions.map((r) => (
            <RegionCard key={r.region} region={r} onAct={handleAct} />
          ))}
        </div>
      </main>

      <aside className="border-l border-surface-300 bg-surface-50 overflow-y-auto">
        <div className="p-5 space-y-5">
          <div>
            <div className="text-meta uppercase tracking-wider text-ink-500">
              Recent distress
            </div>
            <div className="text-sm text-ink-600 mt-1">
              Latest civilian messages flagged distress. Click to open the case.
            </div>
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
}: {
  label: string;
  value: number;
  tone?: "critical" | "high";
}) {
  const color =
    tone === "critical"
      ? "text-sev-critical"
      : tone === "high"
        ? "text-sev-high"
        : "text-ink-900";
  return (
    <div className="flex flex-col items-end">
      <div className="font-mono text-lg leading-none">
        <span className={color}>{value}</span>
      </div>
      <div className="text-meta uppercase tracking-wider text-ink-500 mt-0.5">
        {label}
      </div>
    </div>
  );
}
