import { useEffect, useRef, useState } from "react";
import clsx from "clsx";
import {
  fetchAudiences,
  fetchIncidents,
  fetchMe,
  fetchOperators,
  fetchRegionStats,
  openStream,
  type StreamStatus,
} from "./lib/api";
import { OperatorSwitcher } from "./components/OperatorSwitcher";
import { LiveIndicator } from "./components/LiveIndicator";
import { useStore } from "./lib/store";
import { navigate, useRoute, type Route } from "./lib/router";
import { DashboardView } from "./pages/DashboardView";
import { MessagesView } from "./pages/MessagesView";
import { CasesView } from "./pages/CasesView";
import { MapView } from "./pages/MapView";
import { FilterBar } from "./components/FilterBar";

const TABS: { id: Route; label: string }[] = [
  { id: "dashboard", label: "Dashboard" },
  { id: "messages", label: "Messages" },
  { id: "cases", label: "Cases" },
  { id: "map", label: "Map" },
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
  const activeTab = useRoute();
  const selectedIncidentId = useStore((s) => s.selectedIncidentId);

  const [navOpen, setNavOpen] = useState(false);
  const navRef = useRef<HTMLDivElement>(null);
  const [streamStatus, setStreamStatus] = useState<StreamStatus>("connecting");
  const [lastEventTs, setLastEventTs] = useState<number | null>(null);

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

    const closeStream = openStream(
      (ev) => {
        upsertIncident(ev.incident);
        if (ev.message) appendMessage(ev.message);
        setLastEventTs(Date.now());
      },
      setStreamStatus,
    );

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
      <header className="h-14 border-b border-surface-300 bg-white px-4 sm:px-8 flex items-center justify-between gap-2 shrink-0">
        <div className="flex items-center gap-3 sm:gap-8 min-w-0">
          <button
            onClick={() => navigate("dashboard")}
            className="flex items-center gap-2.5 shrink-0 rounded-sm transition hover:opacity-80"
            aria-label="Go to dashboard"
          >
            <span
              aria-hidden
              className="w-7 h-7 rounded-md bg-ink-900 flex items-center justify-center shrink-0"
            >
              <svg
                viewBox="0 0 32 32"
                fill="none"
                className="w-full h-full"
              >
                <path
                  d="M 8 22 C 8 6 24 6 24 22"
                  stroke="#ffffff"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
                <circle cx="8" cy="22" r="2.5" fill="#ffffff" />
                <circle cx="16" cy="10" r="2.5" fill="#ffffff" />
                <circle cx="24" cy="22" r="2.5" fill="#ffffff" />
              </svg>
            </span>
            <span className="font-sans text-[12px] font-medium uppercase tracking-[0.22em] leading-none whitespace-nowrap text-ink-900">
              SafeThread
            </span>
          </button>
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
                      onClick={() => {
                        navigate(t.id);
                        setNavOpen(false);
                      }}
                      className={clsx(
                        "w-full text-left px-3 py-2.5 text-sm flex items-center justify-between transition",
                        active
                          ? "bg-surface-100 text-ink-900 font-medium"
                          : "text-ink-700 hover:bg-surface-100/60",
                      )}
                    >
                      <span>{t.label}</span>
                      {active && (
                        <span className="w-1.5 h-1.5 rounded-full bg-brand-600" />
                      )}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* desktop tabs */}
          <nav className="hidden md:flex items-center gap-6">
            {TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => navigate(t.id)}
                className={clsx(
                  "py-1.5 text-[13px] font-medium tracking-tight transition whitespace-nowrap",
                  activeTab === t.id
                    ? "text-ink-900"
                    : "text-ink-500 hover:text-ink-900",
                )}
              >
                {t.label}
              </button>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-3 sm:gap-4 shrink-0">
          <span className="hidden md:inline-flex">
            <LiveIndicator status={streamStatus} lastEventTs={lastEventTs} />
          </span>
          <span className="hidden md:block w-px h-3.5 bg-surface-300" />
          <OperatorSwitcher />
        </div>
      </header>

      {activeTab !== "dashboard" && activeTab !== "messages" && (
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
        {activeTab === "messages" && <MessagesView />}
        {activeTab === "cases" && <CasesView />}
        {activeTab === "map" && <MapView />}
      </div>
    </div>
  );
}
