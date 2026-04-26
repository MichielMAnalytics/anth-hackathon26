import { useEffect, useState } from "react";
import { createIncident } from "../lib/api";
import { useStore } from "../lib/store";
import type { Incident, Region } from "../lib/types";

interface Props {
  onClose: () => void;
  onCreated?: (incident: Incident) => void;
  /** Pre-fill values when promoting an inbound message to a case. */
  defaults?: {
    description?: string;
    region?: Region;
    personName?: string;
  };
}

const REGION_OPTIONS: { value: Region; label: string }[] = [
  { value: "IRQ_BAGHDAD", label: "Baghdad, Iraq" },
  { value: "IRQ_MOSUL", label: "Mosul, Iraq" },
  { value: "SYR_ALEPPO", label: "Aleppo, Syria" },
  { value: "SYR_DAMASCUS", label: "Damascus, Syria" },
  { value: "YEM_SANAA", label: "Sana'a, Yemen" },
  { value: "LBN_BEIRUT", label: "Beirut, Lebanon" },
];

const CATEGORY_OPTIONS = [
  { value: "missing_person", label: "Missing person" },
  { value: "medical", label: "Medical" },
  { value: "resource_shortage", label: "Resource shortage" },
  { value: "safety", label: "Safety" },
] as const;

const URGENCY_OPTIONS = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
  { value: "critical", label: "Critical" },
] as const;

type CategoryValue = (typeof CATEGORY_OPTIONS)[number]["value"];
type UrgencyValue = (typeof URGENCY_OPTIONS)[number]["value"];

export function CreateCaseModal({ onClose, onCreated, defaults }: Props) {
  const upsertIncident = useStore((s) => s.upsertIncident);
  const selectIncident = useStore((s) => s.selectIncident);
  const me = useStore((s) => s.me);

  // Default region: explicit override > operator's first allowed region > fallback.
  const defaultRegion: Region =
    defaults?.region ?? (me?.regions[0] as Region) ?? "SYR_ALEPPO";

  const [personName, setPersonName] = useState(defaults?.personName ?? "");
  const [description, setDescription] = useState(defaults?.description ?? "");
  const [region, setRegion] = useState<Region>(defaultRegion);
  const [category, setCategory] = useState<CategoryValue>("missing_person");
  const [urgency, setUrgency] = useState<UrgencyValue>("medium");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ESC closes
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && !submitting) onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose, submitting]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!personName.trim() || !description.trim() || submitting) return;
    setError(null);
    setSubmitting(true);
    try {
      const inc = await createIncident({
        person_name: personName.trim(),
        description: description.trim(),
        region,
        category,
        urgency_tier: urgency,
      });
      // Optimistically upsert so the new card shows up before the WS event lands.
      upsertIncident(inc);
      selectIncident(inc.id);
      onCreated?.(inc);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "create failed");
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
            Create case
          </h2>
          <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-ink-500 mt-1">
            Operator-issued amber alert
          </p>
        </header>

        <div className="px-5 py-4 space-y-4">
          <Field label="Person name">
            <input
              type="text"
              value={personName}
              onChange={(e) => setPersonName(e.target.value)}
              required
              maxLength={200}
              autoFocus
              placeholder="e.g. Maryam, 11"
              className="w-full rounded border border-surface-300 px-3 py-2 text-sm focus:outline-none focus:border-accent-500"
            />
          </Field>

          <Field label="Description">
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              required
              rows={3}
              placeholder="e.g. Last seen at the Aleppo bus station, wearing a red jacket. Travelling alone."
              className="w-full rounded border border-surface-300 px-3 py-2 text-sm focus:outline-none focus:border-accent-500 resize-y"
            />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Region">
              <select
                value={region}
                onChange={(e) => setRegion(e.target.value as Region)}
                className="w-full rounded border border-surface-300 px-3 py-2 text-sm bg-white focus:outline-none focus:border-accent-500"
              >
                {REGION_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Category">
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value as CategoryValue)}
                className="w-full rounded border border-surface-300 px-3 py-2 text-sm bg-white focus:outline-none focus:border-accent-500"
              >
                {CATEGORY_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </Field>
          </div>

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
            disabled={submitting || !personName.trim() || !description.trim()}
            className="px-4 py-1.5 text-sm font-semibold rounded-sm bg-ink-900 text-white hover:bg-ink-800 transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? "Creating…" : "Create case"}
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
