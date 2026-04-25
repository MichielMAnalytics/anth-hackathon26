import { useEffect, useState } from "react";
import { fetchIncidents, openStream, seedDemo } from "./lib/api";
import { useStore } from "./lib/store";
import { IncidentList } from "./components/IncidentList";
import { MessageThread } from "./components/MessageThread";
import { DetailPanel } from "./components/detail/DetailPanel";
import { AmberAlertModal } from "./components/AmberAlertModal";

export function App() {
  const setIncidents = useStore((s) => s.setIncidents);
  const upsertIncident = useStore((s) => s.upsertIncident);
  const appendMessage = useStore((s) => s.appendMessage);
  const select = useStore((s) => s.select);
  const selectedId = useStore((s) => s.selectedId);
  const incident = useStore((s) =>
    s.selectedId ? s.incidents[s.selectedId] : null,
  );
  const [alertOpen, setAlertOpen] = useState(false);
  const [seeding, setSeeding] = useState(false);

  useEffect(() => {
    fetchIncidents().then((list) => {
      setIncidents(list);
      if (list.length > 0 && !useStore.getState().selectedId) {
        select(list[0].id);
      }
    });
    return openStream((ev) => {
      upsertIncident(ev.incident);
      if (ev.message) appendMessage(ev.message);
    });
  }, [setIncidents, upsertIncident, appendMessage, select]);

  async function handleSeed() {
    setSeeding(true);
    await seedDemo();
    const list = await fetchIncidents();
    setIncidents(list);
    if (list.length > 0) select(list[0].id);
    setSeeding(false);
  }

  return (
    <div className="h-full flex flex-col bg-ink-950 text-ink-100">
      <header className="h-12 border-b border-ink-800 px-4 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded bg-sev-critical/20 border border-sev-critical/40 flex items-center justify-center text-sm">
            ◈
          </div>
          <div className="text-sm font-semibold tracking-tight">
            NGO Hub
            <span className="ml-2 text-[11px] font-mono text-ink-500">
              v0.1
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleSeed}
            disabled={seeding}
            className="text-xs px-2.5 py-1 border border-ink-700 text-ink-200 rounded hover:bg-ink-800 disabled:opacity-50"
          >
            {seeding ? "Seeding…" : "Seed demo"}
          </button>
          <div className="text-xs text-ink-400 font-mono">
            operator@ngo
          </div>
        </div>
      </header>

      <div className="flex-1 grid grid-cols-[280px_1fr_360px] min-h-0">
        <aside className="border-r border-ink-800 min-h-0">
          <IncidentList />
        </aside>

        <main className="min-h-0 min-w-0">
          <MessageThread />
        </main>

        <aside className="border-l border-ink-800 min-h-0 flex flex-col">
          <div className="px-5 py-3 border-b border-ink-800">
            <div className="text-xs uppercase tracking-wider text-ink-400">
              Incident detail
            </div>
            <div className="text-sm font-medium text-ink-100">
              {incident ? incident.title : "—"}
            </div>
          </div>
          <div className="flex-1 overflow-y-auto p-5">
            {incident ? (
              <DetailPanel incident={incident} />
            ) : (
              <div className="text-sm text-ink-400">
                Select an incident to see its profile.
              </div>
            )}
          </div>
          {incident && incident.category === "missing_person" && (
            <div className="p-4 border-t border-ink-800">
              <button
                onClick={() => setAlertOpen(true)}
                className="w-full px-3 py-2 bg-sev-critical/90 hover:bg-sev-critical text-white text-sm font-medium rounded"
              >
                ◈ Send Amber Alert
              </button>
            </div>
          )}
        </aside>
      </div>

      {alertOpen && incident && (
        <AmberAlertModal
          incident={incident}
          onClose={() => setAlertOpen(false)}
        />
      )}

      {selectedId === null && null /* keep selectedId in deps */}
    </div>
  );
}
