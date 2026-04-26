import { useEffect, useState } from "react";
import { updateIncident } from "../lib/api";
import { useStore } from "../lib/store";
import type { Incident } from "../lib/types";

interface Props {
  incident: Incident;
  onClose: () => void;
}

const URGENCY_OPTIONS = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
  { value: "critical", label: "Critical" },
] as const;

const STATUS_OPTIONS = [
  { value: "active", label: "Active" },
  { value: "resolved", label: "Resolved" },
  { value: "archived", label: "Archived" },
] as const;

type Urgency = (typeof URGENCY_OPTIONS)[number]["value"];
type Status = (typeof STATUS_OPTIONS)[number]["value"];

const SEVERITY_TO_URGENCY: Record<string, Urgency> = {
  low: "low",
  medium: "medium",
  high: "high",
  critical: "critical",
};

export function EditCaseModal({ incident, onClose }: Props) {
  const upsertIncident = useStore((s) => s.upsertIncident);

  const initialDescription =
    typeof incident.details?.description === "string"
      ? incident.details.description
      : "";
  const [description, setDescription] = useState<string>(initialDescription);
  const [urgency, setUrgency] = useState<Urgency>(
    SEVERITY_TO_URGENCY[incident.severity] ?? "medium",
  );
  const [status, setStatus] = useState<Status>("active");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && !submitting) onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose, submitting]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!description.trim() || submitting) return;
    setError(null);
    setSubmitting(true);
    try {
      const updated = await updateIncident(incident.id, {
        description: description.trim(),
        urgency_tier: urgency,
        status,
      });
      upsertIncident(updated);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "update failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 px-4 pt-16 sm:pt-24"
      onClick={(e) => {
        if (e.target === e.currentTarget && !submitting) onClose();
      }}
    >
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-lg rounded-md bg-white shadow-xl border border-surface-300"
      >
        <header className="px-5 py-4 border-b border-surface-300">
          <h2 className="font-display text-[18px] font-semibold tracking-tight text-ink-900">
            Edit case
          </h2>
          <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-ink-500 mt-1">
            {incident.title} · push update to civilians
          </p>
        </header>

        <div className="px-5 py-4 space-y-4">
          <Field label="Description (this is what civilians see)">
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              required
              rows={4}
              autoFocus
              placeholder="e.g. Maryam was last seen at the Aleppo bus station. Wearing red jacket. Contact us if seen."
              className="w-full rounded border border-surface-300 px-3 py-2 text-sm focus:outline-none focus:border-accent-500 resize-y"
            />
          </Field>

          <Field label="Urgency">
            <div className="flex gap-2">
              {URGENCY_OPTIONS.map((o) => (
                <button
                  key={o.value}
                  type="button"
                  onClick={() => setUrgency(o.value)}
                  className={
                    "flex-1 px-3 py-1.5 text-xs font-mono uppercase tracking-[0.12em] rounded-sm border transition " +
                    (urgency === o.value
                      ? "border-ink-900 bg-ink-900 text-white"
                      : "border-surface-300 bg-white text-ink-700 hover:bg-surface-100")
                  }
                >
                  {o.label}
                </button>
              ))}
            </div>
          </Field>

          <Field label="Status">
            <div className="flex gap-2">
              {STATUS_OPTIONS.map((o) => (
                <button
                  key={o.value}
                  type="button"
                  onClick={() => setStatus(o.value)}
                  className={
                    "flex-1 px-3 py-1.5 text-xs font-mono uppercase tracking-[0.12em] rounded-sm border transition " +
                    (status === o.value
                      ? "border-ink-900 bg-ink-900 text-white"
                      : "border-surface-300 bg-white text-ink-700 hover:bg-surface-100")
                  }
                >
                  {o.label}
                </button>
              ))}
            </div>
          </Field>

          {error && (
            <div className="rounded border border-sev-high/40 bg-sev-high/10 px-3 py-2 text-xs text-sev-high">
              {error}
            </div>
          )}
        </div>

        <footer className="px-5 py-3 border-t border-surface-300 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="px-3 py-1.5 text-sm rounded-sm border border-surface-300 hover:bg-surface-100 transition disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting || !description.trim()}
            className="px-4 py-1.5 text-sm font-semibold rounded-sm bg-ink-900 text-white hover:bg-ink-800 transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? "Saving…" : "Save & push update"}
          </button>
        </footer>
      </form>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block font-mono text-[11px] uppercase tracking-[0.14em] text-ink-500 mb-1.5">
        {label}
      </span>
      {children}
    </label>
  );
}
