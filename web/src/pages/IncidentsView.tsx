import { useState } from "react";
import { useStore } from "../lib/store";
import { IncidentList } from "../components/IncidentList";
import { MessageThread } from "../components/MessageThread";
import { DetailPanel } from "../components/detail/DetailPanel";
import { SendModal } from "../components/send/SendModal";
import type { SendMode } from "../lib/types";

export function IncidentsView() {
  const incident = useStore((s) =>
    s.selectedIncidentId ? s.incidents[s.selectedIncidentId] : null,
  );
  const audiences = useStore((s) => s.audiences);
  const selectedRegion = useStore((s) => s.selectedRegion);
  const [sendMode, setSendMode] = useState<SendMode | null>(null);

  const showAlert = incident?.category === "missing_person";
  const showRequest =
    incident && (incident.category === "medical" ||
      incident.category === "resource_shortage");

  return (
    <div className="h-full grid grid-cols-[300px_1fr_380px] min-h-0">
      <aside className="border-r border-paper-200 bg-paper-50 min-h-0">
        <IncidentList filterRegion={selectedRegion} />
      </aside>
      <main className="min-h-0 min-w-0">
        <MessageThread />
      </main>
      <aside className="border-l border-paper-200 bg-paper-50 min-h-0 flex flex-col">
        <div className="px-6 py-4 border-b border-paper-200">
          <div className="text-meta uppercase tracking-wider text-paper-500">
            Incident detail
          </div>
          <div className="font-display text-xl text-paper-900 mt-0.5 leading-snug">
            {incident ? incident.title : "—"}
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-6">
          {incident ? (
            <DetailPanel incident={incident} />
          ) : (
            <div className="text-sm text-paper-600">
              Select an incident to see its profile.
            </div>
          )}
        </div>
        {incident && (showAlert || showRequest) && (
          <div className="p-4 border-t border-paper-200 space-y-2">
            {showAlert && (
              <button
                onClick={() => setSendMode("alert")}
                className="w-full px-3 py-2.5 bg-accent-600 hover:bg-accent-700 text-paper-50 text-sm font-medium rounded-md"
              >
                Send Amber Alert
              </button>
            )}
            {showRequest && (
              <button
                onClick={() => setSendMode("request")}
                className="w-full px-3 py-2.5 bg-paper-50 hover:bg-paper-100 text-paper-900 border border-paper-300 text-sm font-medium rounded-md"
              >
                Request Help
              </button>
            )}
          </div>
        )}
      </aside>

      {sendMode && incident && (
        <SendModal
          mode={sendMode}
          incident={incident}
          audiences={audiences}
          onClose={() => setSendMode(null)}
        />
      )}
    </div>
  );
}
