import { useState } from "react";
import { useStore } from "../lib/store";
import { IncidentList } from "../components/IncidentList";
import { CaseThread } from "../components/CaseThread";
import { DetailPanel } from "../components/detail/DetailPanel";
import { CaseMiniMap } from "../components/CaseMiniMap";
import { SendModal } from "../components/send/SendModal";
import type { SendMode } from "../lib/types";

export function CasesView() {
  const region = useStore((s) => s.selectedRegion);
  const issue = useStore((s) => s.issueFilter);
  const incident = useStore((s) =>
    s.selectedIncidentId ? s.incidents[s.selectedIncidentId] : null,
  );
  const audiences = useStore((s) => s.audiences);
  const [sendMode, setSendMode] = useState<SendMode | null>(null);

  return (
    <div className="h-full grid grid-cols-[300px_1fr_360px] min-h-0">
      <aside className="border-r border-surface-300 bg-surface-50 min-h-0">
        <IncidentList region={region} issue={issue} />
      </aside>

      <main className="min-h-0 min-w-0">
        <CaseThread />
      </main>

      <aside className="border-l border-surface-300 bg-white min-h-0 flex flex-col">
        <div className="px-5 py-3.5 border-b border-surface-300">
          <div className="text-meta uppercase tracking-wider text-ink-500">
            Case profile
          </div>
          <div className="font-display text-lg font-semibold text-ink-900 mt-0.5 leading-snug">
            {incident ? incident.title : "—"}
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {incident ? (
            <>
              <CaseMiniMap incident={incident} />
              <DetailPanel incident={incident} />
            </>
          ) : (
            <div className="text-sm text-ink-500">
              Select a case to see its profile.
            </div>
          )}
        </div>
        {incident && (
          <div className="p-4 border-t border-surface-300 space-y-2">
            {incident.category === "missing_person" && (
              <button
                onClick={() => setSendMode("alert")}
                className="w-full px-3 py-2.5 bg-brand-600 hover:bg-brand-700 text-white text-sm font-semibold rounded-md"
              >
                Send Amber Alert broadcast
              </button>
            )}
            {(incident.category === "medical" ||
              incident.category === "resource_shortage") && (
              <button
                onClick={() => setSendMode("request")}
                className="w-full px-3 py-2.5 bg-brand-600 hover:bg-brand-700 text-white text-sm font-semibold rounded-md"
              >
                Request help broadcast
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
