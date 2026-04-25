import { useEffect, useRef, useState } from "react";
import clsx from "clsx";
import {
  fetchAudiences,
  fetchIncidents,
  fetchMe,
  fetchOperators,
  fetchRegionStats,
  openStream,
} from "./lib/api";
import { OperatorSwitcher } from "./components/OperatorSwitcher";
import { useStore, type Tab } from "./lib/store";
import { DashboardView } from "./pages/DashboardView";
import { CasesView } from "./pages/CasesView";
import { MapView } from "./pages/MapView";
import { FilterBar } from "./components/FilterBar";

const TABS: { id: Tab; label: string; enabled: boolean }[] = [
  { id: "dashboard", label: "Dashboard", enabled: true },
  { id: "cases", label: "Cases", enabled: true },
  { id: "map", label: "Map", enabled: true },
  { id: "stream", label: "Stream", enabled: false },
];

export function App() {
  const setIncidents = useStore((s) => s.setIncidents);
  const upsertIncident = useStore((s) => s.upsertIncident);
  const appendMessage = useStore((s) => s.appendMessage);
  const setAudiences = useStore((s) => s.setAudiences);
  const setRegions = useStore((s) => s.setRegions);
  const setMe = useStore((s) => s.setMe);
  const setOperators = useStore((s) => s.setOperators);
  const select = useStore((s) => s.selectIncident);
  const activeTab = useStore((s) => s.activeTab);
  const setTab = useStore((s) => s.setTab);
  const selectedIncidentId = useStore((s) => s.selectedIncidentId);

  const [navOpen, setNavOpen] = useState(false);
  const navRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (navRef.current && !navRef.current.contains(e.target as Node)) {
        setNavOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  useEffect(() => {
    Promise.all([
      fetchIncidents(),
      fetchAudiences(),
      fetchRegionStats(),
      fetchMe(),
      fetchOperators(),
    ]).then(([incidents, audiences, regions, me, operators]) => {
      setIncidents(incidents);
      setAudiences(audiences);
      setRegions(regions);
      setMe(me);
      setOperators(operators);
      if (incidents.length > 0 && !useStore.getState().selectedIncidentId) {
        select(incidents[0].id);
      }
    });

    const closeStream = openStream((ev) => {
      upsertIncident(ev.incident);
      if (ev.message) appendMessage(ev.message);
    });

    const tick = setInterval(() => {
      fetchRegionStats().then(setRegions).catch(() => {});
    }, 10000);

    return () => {
      closeStream();
      clearInterval(tick);
    };
  }, [
    setIncidents,
    upsertIncident,
    appendMessage,
    setAudiences,
    setRegions,
    setMe,
    setOperators,
    select,
  ]);

  return (
    <div className="h-full flex flex-col bg-surface-100 text-ink-900">
      <header className="h-14 border-b border-surface-300 bg-white px-3 sm:px-6 flex items-center justify-between gap-2 shrink-0">
        <div className="flex items-center gap-3 sm:gap-6 min-w-0">
          <div className="flex items-center gap-2 sm:gap-2.5 shrink-0">
            <div className="w-7 h-7 rounded bg-brand-600 flex items-center justify-center text-white font-bold text-sm leading-none">
              W
            </div>
            <div className="hidden sm:block font-display text-base font-bold text-ink-900 tracking-tight whitespace-nowrap">
              War Child
              <span className="ml-1.5 text-ink-500 font-medium">
                · Field Hub
              </span>
            </div>
          </div>
          {/* mobile burger menu */}
          <div ref={navRef} className="md:hidden relative">
            <button
              onClick={() => setNavOpen((o) => !o)}
              className="flex items-center gap-2 px-2.5 py-1.5 text-sm font-medium text-ink-900 rounded-md hover:bg-surface-100 border border-surface-300"
              aria-label="Open navigation"
              aria-expanded={navOpen}
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M2 3h10M2 7h10M2 11h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
              {TABS.find((t) => t.id === activeTab)?.label ?? "Menu"}
            </button>
            {navOpen && (
              <div className="absolute left-0 top-full mt-1.5 z-[1000] w-44 bg-white border border-surface-300 rounded-md shadow-modal overflow-hidden">
                {TABS.map((t) => {
                  const active = t.id === activeTab;
                  return (
                    <button
                      key={t.id}
                      disabled={!t.enabled}
                      onClick={() => {
                        if (!t.enabled) return;
                        setTab(t.id);
                        setNavOpen(false);
                      }}
                      className={clsx(
                        "w-full text-left px-3 py-2.5 text-sm flex items-center justify-between transition",
                        !t.enabled && "text-ink-400 cursor-not-allowed",
                        t.enabled && active && "bg-brand-50/60 text-ink-900 font-medium",
                        t.enabled && !active && "text-ink-700 hover:bg-surface-50",
                      )}
                    >
                      <span>{t.label}</span>
                      {!t.enabled && (
                        <span className="text-meta uppercase tracking-wider text-ink-400">
                          soon
                        </span>
                      )}
                      {t.enabled && active && (
                        <span className="text-brand-600 text-sm leading-none">●</span>
                      )}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* desktop tabs */}
          <nav className="hidden md:flex items-center gap-0.5">
            {TABS.map((t) => (
              <button
                key={t.id}
                disabled={!t.enabled}
                onClick={() => t.enabled && setTab(t.id)}
                className={clsx(
                  "relative px-3.5 py-1.5 text-sm font-medium rounded-md transition whitespace-nowrap",
                  !t.enabled && "text-ink-400 cursor-not-allowed hidden lg:inline-flex",
                  t.enabled && activeTab === t.id
                    ? "text-ink-900"
                    : t.enabled && "text-ink-600 hover:text-ink-900",
                )}
              >
                {t.label}
                {!t.enabled && (
                  <span className="ml-1.5 text-meta uppercase tracking-wider text-ink-400">
                    soon
                  </span>
                )}
                {t.enabled && activeTab === t.id && (
                  <span className="absolute -bottom-[15px] left-3.5 right-3.5 h-0.5 bg-brand-600 rounded-full" />
                )}
              </button>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-2 sm:gap-3 shrink-0">
          <OperatorSwitcher />
        </div>
      </header>

      {activeTab !== "dashboard" && (
        <div
          className={
            activeTab === "cases" && selectedIncidentId
              ? "hidden md:block"
              : ""
          }
        >
          <FilterBar />
        </div>
      )}

      <div className="flex-1 min-h-0">
        {activeTab === "dashboard" && <DashboardView />}
        {activeTab === "cases" && <CasesView />}
        {activeTab === "map" && <MapView />}
      </div>
    </div>
  );
}
