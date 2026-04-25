import { useEffect, useState } from "react";
import clsx from "clsx";
import {
  fetchAudiences,
  fetchIncidents,
  fetchRegionStats,
  openStream,
  seedDemo,
} from "./lib/api";
import { useStore, type Tab } from "./lib/store";
import { MapView } from "./pages/MapView";
import { IncidentsView } from "./pages/IncidentsView";

const TABS: { id: Tab; label: string; enabled: boolean }[] = [
  { id: "map", label: "Map", enabled: true },
  { id: "incidents", label: "Incidents", enabled: true },
  { id: "stream", label: "Stream", enabled: false },
];

export function App() {
  const setIncidents = useStore((s) => s.setIncidents);
  const upsertIncident = useStore((s) => s.upsertIncident);
  const appendMessage = useStore((s) => s.appendMessage);
  const setAudiences = useStore((s) => s.setAudiences);
  const setRegions = useStore((s) => s.setRegions);
  const select = useStore((s) => s.selectIncident);
  const activeTab = useStore((s) => s.activeTab);
  const setTab = useStore((s) => s.setTab);

  const [seeding, setSeeding] = useState(false);

  useEffect(() => {
    Promise.all([fetchIncidents(), fetchAudiences(), fetchRegionStats()]).then(
      ([incidents, audiences, regions]) => {
        setIncidents(incidents);
        setAudiences(audiences);
        setRegions(regions);
        if (incidents.length > 0 && !useStore.getState().selectedIncidentId) {
          select(incidents[0].id);
        }
      },
    );

    const closeStream = openStream((ev) => {
      upsertIncident(ev.incident);
      if (ev.message) appendMessage(ev.message);
    });

    const tick = setInterval(() => {
      fetchRegionStats().then(setRegions).catch(() => {});
    }, 8000);

    return () => {
      closeStream();
      clearInterval(tick);
    };
  }, [setIncidents, upsertIncident, appendMessage, setAudiences, setRegions, select]);

  async function handleSeed() {
    setSeeding(true);
    await seedDemo();
    const [incidents, regions] = await Promise.all([
      fetchIncidents(),
      fetchRegionStats(),
    ]);
    setIncidents(incidents);
    setRegions(regions);
    if (incidents.length > 0) select(incidents[0].id);
    setSeeding(false);
  }

  return (
    <div className="h-full flex flex-col bg-paper-50 text-paper-900">
      <header className="h-14 border-b border-paper-200 bg-paper-50/95 backdrop-blur-sm px-6 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-md bg-accent-600 flex items-center justify-center text-paper-50 font-display text-sm leading-none">
              N
            </div>
            <div className="font-display text-lg text-paper-900 tracking-tight">
              NGO Hub
              <span className="ml-2 text-meta font-mono uppercase tracking-wider text-paper-500 align-middle">
                v0.2
              </span>
            </div>
          </div>
          <nav className="flex items-center gap-1">
            {TABS.map((t) => (
              <button
                key={t.id}
                disabled={!t.enabled}
                onClick={() => t.enabled && setTab(t.id)}
                className={clsx(
                  "relative px-3.5 py-1.5 text-sm font-medium rounded-md transition",
                  !t.enabled && "text-paper-400 cursor-not-allowed",
                  t.enabled && activeTab === t.id
                    ? "text-paper-900 bg-paper-100"
                    : t.enabled && "text-paper-600 hover:text-paper-900",
                )}
              >
                {t.label}
                {!t.enabled && (
                  <span className="ml-1.5 text-meta uppercase tracking-wider text-paper-400">
                    soon
                  </span>
                )}
                {t.enabled && activeTab === t.id && (
                  <span className="absolute -bottom-[15px] left-3.5 right-3.5 h-0.5 bg-accent-600 rounded-full" />
                )}
              </button>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleSeed}
            disabled={seeding}
            className="text-sm px-3 py-1.5 border border-paper-300 text-paper-700 rounded-md hover:bg-paper-100 disabled:opacity-50"
          >
            {seeding ? "Seeding…" : "Seed demo"}
          </button>
          <div className="flex items-center gap-2 text-meta font-mono text-paper-600 px-2.5 py-1 rounded-full border border-paper-200 bg-paper-50">
            <span className="w-1.5 h-1.5 rounded-full bg-sev-low" />
            operator@ngo
          </div>
        </div>
      </header>

      <div className="flex-1 min-h-0">
        {activeTab === "map" && <MapView />}
        {activeTab === "incidents" && <IncidentsView />}
      </div>
    </div>
  );
}
