import { useState } from "react";
import clsx from "clsx";
import { useStore } from "../lib/store";
import { IncidentList } from "../components/IncidentList";
import { CaseThread } from "../components/CaseThread";
import { DetailPanel } from "../components/detail/DetailPanel";
import { CaseMiniMap } from "../components/CaseMiniMap";
import { SendModal } from "../components/send/SendModal";
import type { SendMode } from "../lib/types";

type MobilePane = "list" | "thread" | "profile";

export function CasesView() {
  const region = useStore((s) => s.selectedRegion);
  const issue = useStore((s) => s.issueFilter);
  const incident = useStore((s) =>
    s.selectedIncidentId ? s.incidents[s.selectedIncidentId] : null,
  );
  const audiences = useStore((s) => s.audiences);
  const selectIncident = useStore((s) => s.selectIncident);
  const [sendMode, setSendMode] = useState<SendMode | null>(null);
  // Mobile-only nav state. On md+ all panes are visible regardless.
  const [mobilePane, setMobilePane] = useState<MobilePane>("list");

  // when a case is selected on mobile, jump straight to its thread
  const showList = !incident || mobilePane === "list";
  const showThread = !!incident && mobilePane === "thread";
  const showProfile = !!incident && mobilePane === "profile";

  function openCase() {
    setMobilePane("thread");
  }

  return (
    <div className="h-full md:grid md:grid-cols-[300px_1fr_360px] min-h-0 relative">
      <aside
        className={clsx(
          "border-r border-surface-300 bg-surface-50 min-h-0 h-full",
          "md:block",
          showList ? "block" : "hidden md:block",
        )}
        onClick={() => {
          // mobile: when the user clicks a case, the IncidentList already
          // sets selectedIncidentId; we then jump to the thread pane.
          if (window.matchMedia("(max-width: 767px)").matches) openCase();
        }}
      >
        <IncidentList region={region} issue={issue} />
      </aside>

      <main
        className={clsx(
          "min-h-0 min-w-0 h-full flex-col",
          "md:flex",
          showThread ? "flex" : "hidden md:flex",
        )}
      >
        {/* mobile back / profile bar */}
        {incident && (
          <div className="md:hidden flex items-center gap-2 px-3 py-2 border-b border-surface-300 bg-white">
            <button
              onClick={() => {
                setMobilePane("list");
                selectIncident(null);
              }}
              className="px-2.5 py-1 text-sm text-ink-700 hover:bg-surface-100 rounded-md"
              aria-label="Back to cases list"
            >
              ← Cases
            </button>
            <div className="text-sm font-semibold text-ink-900 truncate flex-1">
              {incident.title}
            </div>
            <button
              onClick={() => setMobilePane("profile")}
              className="px-2.5 py-1 text-sm text-ink-700 border border-surface-300 rounded-md hover:bg-surface-100"
            >
              Profile
            </button>
          </div>
        )}
        <div className="flex-1 min-h-0">
          <CaseThread />
        </div>
      </main>

      {/* desktop right rail */}
      <aside className="hidden md:flex border-l border-surface-300 bg-white min-h-0 flex-col">
        <CaseProfile
          incident={incident}
          onAlert={() => setSendMode("alert")}
          onRequest={() => setSendMode("request")}
        />
      </aside>

      {/* mobile profile sheet */}
      {showProfile && incident && (
        <div className="md:hidden absolute inset-0 z-30 bg-white flex flex-col">
          <div className="flex items-center gap-2 px-3 py-2 border-b border-surface-300">
            <button
              onClick={() => setMobilePane("thread")}
              className="px-2.5 py-1 text-sm text-ink-700 hover:bg-surface-100 rounded-md"
              aria-label="Back to thread"
            >
              ← Thread
            </button>
            <div className="text-sm font-semibold text-ink-900 truncate flex-1">
              Case profile
            </div>
          </div>
          <div className="flex-1 min-h-0 flex flex-col">
            <CaseProfile
              incident={incident}
              onAlert={() => setSendMode("alert")}
              onRequest={() => setSendMode("request")}
            />
          </div>
        </div>
      )}

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

function CaseProfile({
  incident,
  onAlert,
  onRequest,
}: {
  incident: ReturnType<typeof useStore.getState>["incidents"][string] | null;
  onAlert: () => void;
  onRequest: () => void;
}) {
  if (!incident) {
    return (
      <>
        <div className="px-5 py-3.5 border-b border-surface-300">
          <div className="text-meta uppercase tracking-wider text-ink-500">
            Case profile
          </div>
          <div className="font-display text-lg font-semibold text-ink-900 mt-0.5 leading-snug">
            —
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-5 text-sm text-ink-500">
          Select a case to see its profile.
        </div>
      </>
    );
  }
  return (
    <>
      <div className="px-5 py-3.5 border-b border-surface-300">
        <div className="text-meta uppercase tracking-wider text-ink-500">
          Case profile
        </div>
        <div className="font-display text-lg font-semibold text-ink-900 mt-0.5 leading-snug">
          {incident.title}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-5 space-y-5">
        <CaseMiniMap incident={incident} />
        <DetailPanel incident={incident} />
      </div>
      {(incident.category === "missing_person" ||
        incident.category === "medical" ||
        incident.category === "resource_shortage") && (
        <div className="p-4 border-t border-surface-300 space-y-2">
          {incident.category === "missing_person" && (
            <button
              onClick={onAlert}
              className="w-full px-3 py-2.5 bg-brand-600 hover:bg-brand-700 text-white text-sm font-semibold rounded-md"
            >
              Send Amber Alert broadcast
            </button>
          )}
          {(incident.category === "medical" ||
            incident.category === "resource_shortage") && (
            <button
              onClick={onRequest}
              className="w-full px-3 py-2.5 bg-brand-600 hover:bg-brand-700 text-white text-sm font-semibold rounded-md"
            >
              Request help broadcast
            </button>
          )}
        </div>
      )}
    </>
  );
}
