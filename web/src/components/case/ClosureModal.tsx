import { useEffect, useState } from "react";
import { closeCase } from "../../lib/api";
import type { ClosureReason, Incident } from "../../lib/types";
import { useStore } from "../../lib/store";

interface Props {
  incident: Incident;
  onClose: () => void;
}

const REASONS: { id: ClosureReason; label: string; hint: string }[] = [
  { id: "reunified", label: "Reunified", hint: "Child reunited with family." },
  {
    id: "referred_on",
    label: "Referred on",
    hint: "Handed off to a partner NGO.",
  },
  { id: "aged_out", label: "Aged out", hint: "No longer a minor case." },
  { id: "deceased", label: "Deceased", hint: "Confirmed deceased." },
  {
    id: "lost_contact",
    label: "Lost contact",
    hint: "Unable to reach for an extended period.",
  },
];

export function ClosureModal({ incident, onClose }: Props) {
  const [reason, setReason] = useState<ClosureReason>("reunified");
  const [notes, setNotes] = useState("");
  const [witnessName, setWitnessName] = useState("");
  const [saving, setSaving] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const upsertIncident = useStore((s) => s.upsertIncident);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function save() {
    if (!witnessName.trim()) {
      setError("Witness name is required.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const updated = await closeCase(incident.id, {
        reason,
        notes: notes.trim(),
        witnessName: witnessName.trim(),
      });
      upsertIncident(updated);
      setDone(true);
      setTimeout(onClose, 1200);
    } catch {
      setError("Could not close case. Try again.");
      setSaving(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 bg-ink-900/40 backdrop-blur-sm flex items-start justify-center p-4 overflow-y-auto"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg bg-white border border-surface-300 rounded-xl shadow-modal mt-12"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-6 py-5 border-b border-surface-300 flex items-start justify-between">
          <div>
            <div className="text-meta uppercase tracking-wider text-ink-500">
              Close case
            </div>
            <h2 className="font-display text-xl font-semibold text-ink-900 mt-0.5">
              Mark case closed
            </h2>
            <div className="text-sm text-ink-600 mt-1">
              Closure is logged in the audit trail. The case stays visible but
              dimmed.
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-9 h-9 flex items-center justify-center text-ink-500 hover:text-ink-900 hover:bg-surface-100 rounded-full text-2xl leading-none shrink-0"
            aria-label="Close"
          >
            ×
          </button>
        </div>
        <div className="p-6 space-y-4">
          <div>
            <div className="text-meta uppercase tracking-wider text-ink-500 mb-2">
              Outcome
            </div>
            <div className="space-y-1.5">
              {REASONS.map((r) => (
                <label
                  key={r.id}
                  className="flex items-start gap-3 px-3 py-2 border border-surface-300 rounded-md cursor-pointer hover:bg-surface-50"
                >
                  <input
                    type="radio"
                    name="reason"
                    value={r.id}
                    checked={reason === r.id}
                    onChange={() => setReason(r.id)}
                    className="mt-1 accent-brand-600"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-ink-900">
                      {r.label}
                    </div>
                    <div className="text-xs text-ink-600 mt-0.5">{r.hint}</div>
                  </div>
                </label>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-meta uppercase tracking-wider text-ink-500 mb-1.5">
              Notes
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Optional context for the audit trail."
              className="w-full bg-white border border-surface-300 rounded-md px-3 py-2 text-sm text-ink-900 leading-relaxed focus:outline-none focus:border-brand-600 focus:ring-1 focus:ring-brand-600/20 min-h-[80px]"
            />
          </div>
          <div>
            <label className="block text-meta uppercase tracking-wider text-ink-500 mb-1.5">
              Witness name
            </label>
            <input
              type="text"
              value={witnessName}
              onChange={(e) => setWitnessName(e.target.value)}
              placeholder="e.g. Field worker Aisha"
              className="w-full bg-white border border-surface-300 rounded-md px-3 py-2 text-sm text-ink-900 focus:outline-none focus:border-brand-600 focus:ring-1 focus:ring-brand-600/20"
            />
          </div>
          {error && (
            <div className="rounded-md border border-sev-critical/30 bg-sev-critical/5 p-2.5 text-sm text-sev-critical">
              {error}
            </div>
          )}
          {done && (
            <div className="rounded-md border border-sev-low/30 bg-sev-low/5 p-2.5 text-sm text-sev-low">
              Case closed.
            </div>
          )}
        </div>
        <div className="px-6 py-4 border-t border-surface-300 flex items-center justify-end gap-2">
          <button
            onClick={onClose}
            className="px-3 py-2 text-sm text-ink-700 hover:text-ink-900 rounded-md"
          >
            Cancel
          </button>
          <button
            onClick={save}
            disabled={saving || done}
            className="px-4 py-2 text-sm font-medium bg-brand-600 hover:bg-brand-700 text-white rounded-md disabled:opacity-50"
          >
            {done ? "✓ Closed" : saving ? "Closing…" : "Close case"}
          </button>
        </div>
      </div>
    </div>
  );
}
