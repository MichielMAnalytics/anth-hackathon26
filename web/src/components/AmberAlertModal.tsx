import { useEffect, useState } from "react";
import type { Incident } from "../lib/types";
import { sendAlert } from "../lib/api";

interface Props {
  incident: Incident;
  onClose: () => void;
}

export function AmberAlertModal({ incident, onClose }: Props) {
  const d = incident.details as Record<string, string | undefined>;
  const [name, setName] = useState(d.name ?? "");
  const [photoUrl, setPhotoUrl] = useState(d.photoUrl ?? "");
  const [lastSeenLocation, setLastSeenLocation] = useState(
    d.lastSeenLocation ?? "",
  );
  const [description, setDescription] = useState(d.description ?? "");
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function submit() {
    setSending(true);
    await sendAlert({
      incidentId: incident.id,
      name,
      photoUrl: photoUrl || undefined,
      lastSeenLocation: lastSeenLocation || undefined,
      description: description || undefined,
    });
    setSending(false);
    setSent(true);
    setTimeout(onClose, 1200);
  }

  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-xl bg-ink-900 border border-ink-700 rounded-lg shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-5 py-4 border-b border-ink-800 flex items-center justify-between">
          <div>
            <div className="text-xs uppercase tracking-wider text-sev-critical">
              Amber Alert
            </div>
            <div className="text-base font-semibold text-ink-100">
              Compose broadcast
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-ink-400 hover:text-ink-100 text-xl"
          >
            ×
          </button>
        </div>
        <div className="p-5 space-y-4">
          <Labeled label="Name">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="input"
            />
          </Labeled>
          <Labeled label="Photo URL">
            <input
              value={photoUrl}
              onChange={(e) => setPhotoUrl(e.target.value)}
              className="input"
              placeholder="https://…"
            />
          </Labeled>
          <Labeled label="Last seen location">
            <input
              value={lastSeenLocation}
              onChange={(e) => setLastSeenLocation(e.target.value)}
              className="input"
            />
          </Labeled>
          <Labeled label="Description">
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="input min-h-[90px]"
            />
          </Labeled>
        </div>
        <div className="px-5 py-4 border-t border-ink-800 flex items-center justify-between">
          <div className="text-xs text-ink-500">
            Stub: this will be wired to the mesh transport later.
          </div>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="px-3 py-1.5 text-sm text-ink-300 hover:text-ink-100"
            >
              Cancel
            </button>
            <button
              onClick={submit}
              disabled={sending || sent || !name}
              className="px-4 py-1.5 text-sm font-medium bg-sev-critical/90 hover:bg-sev-critical text-white rounded disabled:opacity-50"
            >
              {sent ? "✓ Queued" : sending ? "Sending…" : "Send alert"}
            </button>
          </div>
        </div>
      </div>
      <style>{`
        .input {
          width: 100%;
          background: #11141a;
          border: 1px solid #272d38;
          border-radius: 6px;
          padding: 8px 10px;
          color: #eceef2;
          font-size: 13px;
          outline: none;
        }
        .input:focus {
          border-color: #5a6473;
        }
      `}</style>
    </div>
  );
}

function Labeled({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <div className="text-[10px] uppercase tracking-wider text-ink-500 mb-1">
        {label}
      </div>
      {children}
    </label>
  );
}
