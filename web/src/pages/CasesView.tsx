import { useState } from "react";
import clsx from "clsx";
import { useStore } from "../lib/store";
import { IncidentList } from "../components/IncidentList";
import { CaseThread } from "../components/CaseThread";
import { DetailPanel } from "../components/detail/DetailPanel";
import { CaseMiniMap } from "../components/CaseMiniMap";
import { SendModal } from "../components/send/SendModal";
import { CreateCaseModal } from "../components/CreateCaseModal";
import { EditCaseModal } from "../components/EditCaseModal";
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
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  // Mobile-only nav state. On md+ all panes are visible regardless.
  const [mobilePane, setMobilePane] = useState<MobilePane>("list");
  // md+ profile rail collapse state. Default open on every mount; persists for
  // the life of the component. lg defaults still open per design.
  const [profileOpen, setProfileOpen] = useState(true);

  // when a case is selected on mobile, jump straight to its thread
  const showList = !incident || mobilePane === "list";
  const showThread = !!incident && mobilePane === "thread";
  const showProfile = !!incident && mobilePane === "profile";

  function openCase() {
    setMobilePane("thread");
  }

  // Grid template depends on whether the right rail is open (md+ only).
  // When collapsed we drop the third track entirely so the thread fills space.
  const gridCols = profileOpen
    ? "md:grid-cols-[240px_1fr_280px] lg:grid-cols-[300px_1fr_360px]"
    : "md:grid-cols-[240px_1fr] lg:grid-cols-[300px_1fr]";

  return (
    <div
      className={clsx(
        "h-full md:grid min-h-0 relative",
        gridCols,
      )}
    >
      <aside
        className={clsx(
          "border-r border-surface-300 bg-surface-50 min-h-0 h-full flex flex-col",
          "md:flex",
          showList ? "flex" : "hidden md:flex",
        )}
        onClick={() => {
          // mobile: when the user clicks a case, the IncidentList already
          // sets selectedIncidentId; we then jump to the thread pane.
          if (window.matchMedia("(max-width: 767px)").matches) openCase();
        }}
      >
        <div className="px-3 py-2 border-b border-surface-300 bg-white flex-shrink-0">
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setCreateOpen(true);
            }}
            className="w-full px-3 py-2 text-sm font-semibold rounded-sm bg-ink-900 text-white hover:bg-ink-800 transition flex items-center justify-center gap-1.5"
          >
            <span className="text-base leading-none">+</span> Create case
          </button>
        </div>
        <div className="flex-1 min-h-0 overflow-auto">
          <IncidentList region={region} issue={issue} />
        </div>
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
              className="px-2.5 py-1 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-700 hover:bg-surface-100 rounded-sm transition"
              aria-label="Back to cases list"
            >
              ← Cases
            </button>
            <div className="font-display text-[14px] font-semibold tracking-tight text-ink-900 truncate flex-1">
              {incident.title}
            </div>
            <button
              onClick={() => setMobilePane("profile")}
              className="px-2.5 py-1 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-700 border border-surface-300 rounded-sm hover:bg-surface-100 transition"
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
      {profileOpen && (
        <aside className="hidden md:flex border-l border-surface-300 bg-white min-h-0 flex-col">
          <CaseProfile
            incident={incident}
            onAlert={() => setSendMode("alert")}
            onRequest={() => setSendMode("request")}
            onEdit={() => setEditOpen(true)}
            onCollapse={() => setProfileOpen(false)}
          />
        </aside>
      )}

      {/* floating re-open handle when collapsed (md+ only) */}
      {!profileOpen && (
        <button
          type="button"
          onClick={() => setProfileOpen(true)}
          aria-label="Show case profile"
          className="hidden md:flex absolute top-3 right-3 z-20 items-center gap-2 px-3 h-9 bg-white border border-surface-300 rounded-sm font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-700 hover:bg-surface-100 hover:border-ink-400 transition"
        >
          <svg width="9" height="9" viewBox="0 0 10 10" fill="none">
            <path d="M6.5 1.5L3 5L6.5 8.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span>Profile</span>
        </button>
      )}

      {/* mobile profile sheet */}
      {showProfile && incident && (
        <div className="md:hidden absolute inset-0 z-30 bg-white flex flex-col">
          <div className="flex items-center gap-2 px-3 py-2 border-b border-surface-300">
            <button
              onClick={() => setMobilePane("thread")}
              className="px-2.5 py-1 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-700 hover:bg-surface-100 rounded-sm transition"
              aria-label="Back to thread"
            >
              ← Thread
            </button>
            <div className="font-display text-[14px] font-semibold tracking-tight text-ink-900 truncate flex-1">
              Case profile
            </div>
          </div>
          <div className="flex-1 min-h-0 flex flex-col">
            <CaseProfile
              incident={incident}
              onAlert={() => setSendMode("alert")}
              onRequest={() => setSendMode("request")}
              onEdit={() => setEditOpen(true)}
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

      {createOpen && <CreateCaseModal onClose={() => setCreateOpen(false)} />}

      {editOpen && incident && (
        <EditCaseModal incident={incident} onClose={() => setEditOpen(false)} />
      )}
    </div>
  );
}

function CaseProfile({
  incident,
  onAlert,
  onRequest,
  onEdit,
  onCollapse,
}: {
  incident: ReturnType<typeof useStore.getState>["incidents"][string] | null;
  onAlert: () => void;
  onRequest: () => void;
  onEdit: () => void;
  onCollapse?: () => void;
}) {
  if (!incident) {
    return (
      <>
        <div className="px-5 py-5 border-b border-surface-300 flex items-start gap-2">
          <div className="flex-1 min-w-0">
            <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">
              /// Case profile
            </div>
            <div className="font-display text-[18px] font-semibold text-ink-900 mt-1.5 leading-snug tracking-tighter">
              —
            </div>
          </div>
          {onCollapse && (
            <CollapseButton onClick={onCollapse} />
          )}
        </div>
        <div className="flex-1 overflow-y-auto p-5 text-[13px] text-ink-500">
          Select a case to see its profile.
        </div>
      </>
    );
  }
  return (
    <>
      <div className="px-5 py-5 border-b border-surface-300 flex items-start gap-2">
        <div className="flex-1 min-w-0">
          <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">
            /// Case profile
          </div>
          <div className="font-display text-[20px] font-semibold text-ink-900 mt-1.5 leading-tight tracking-tighter">
            {incident.title}
          </div>
        </div>
        <button
          type="button"
          onClick={onEdit}
          className="px-2.5 py-1 font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-700 border border-surface-300 rounded-sm hover:bg-surface-100 hover:border-ink-400 transition shrink-0"
          aria-label="Edit case and push update"
        >
          Edit
        </button>
        {onCollapse && <CollapseButton onClick={onCollapse} />}
      </div>
      <div className="flex-1 overflow-y-auto p-5 space-y-6">
        <CaseMiniMap incident={incident} />
        <DetailPanel incident={incident} />
      </div>
      {(incident.category === "missing_person" ||
        incident.category === "medical" ||
        incident.category === "resource_shortage") && (
        <div className="p-4 border-t border-surface-300">
          {incident.category === "missing_person" && (
            <button
              onClick={onAlert}
              className="w-full px-3 py-3 bg-brand-600 hover:bg-brand-700 text-white font-mono text-[11px] uppercase tracking-[0.14em] font-semibold rounded-sm transition"
            >
              Send Amber Alert broadcast
            </button>
          )}
          {(incident.category === "medical" ||
            incident.category === "resource_shortage") && (
            <button
              onClick={onRequest}
              className="w-full px-3 py-3 bg-brand-600 hover:bg-brand-700 text-white font-mono text-[11px] uppercase tracking-[0.14em] font-semibold rounded-sm transition"
            >
              Request help broadcast
            </button>
          )}
        </div>
      )}
    </>
  );
}

function CollapseButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="Hide case profile"
      className="hidden md:inline-flex h-7 w-7 items-center justify-center rounded-sm text-ink-500 hover:bg-surface-100 hover:text-ink-900 shrink-0 transition"
    >
      <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
        <path d="M3.5 1.5L7 5L3.5 8.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </button>
  );
}
