import { useEffect, useState } from "react";
import { patchCaseConsent } from "../../lib/api";
import type { Consent, Incident } from "../../lib/types";
import { useStore } from "../../lib/store";

interface Props {
  incident: Incident;
  onClose: () => void;
}

export function ConsentModal({ incident, onClose }: Props) {
  const existing = (incident.details.consent ?? null) as Consent | null;
  const [dataStorage, setDataStorage] = useState<boolean>(
    existing?.dataStorage ?? true,
  );
  const [referralSharing, setReferralSharing] = useState<boolean>(
    existing?.referralSharing ?? true,
  );
  const [publicBroadcast, setPublicBroadcast] = useState<boolean>(
    existing?.publicBroadcast ?? false,
  );
  const [witnessName, setWitnessName] = useState<string>(
    existing?.witnessName ?? "",
  );
  const [saving, setSaving] = useState(false);
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
      const updated = await patchCaseConsent(incident.id, {
        dataStorage,
        referralSharing,
        publicBroadcast,
        witnessName: witnessName.trim(),
      });
      upsertIncident(updated);
      onClose();
    } catch {
      setError("Could not save consent. Try again.");
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
              Capture consent
            </div>
            <h2 className="font-display text-xl font-semibold text-ink-900 mt-0.5">
              Record guardian consent
            </h2>
            <div className="text-sm text-ink-600 mt-1">
              Captured under the eye of a witnessing case worker. Required
              before any public broadcast.
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
          <Toggle
            label="Store case data securely"
            hint="Required to keep the case file at all."
            value={dataStorage}
            onChange={setDataStorage}
          />
          <Toggle
            label="Share with referral partners"
            hint="Allows handoff to medical / legal / shelter NGOs."
            value={referralSharing}
            onChange={setReferralSharing}
          />
          <Toggle
            label="Permit public broadcast"
            hint="Required to send Amber-style alerts to civilians."
            value={publicBroadcast}
            onChange={setPublicBroadcast}
          />
          <div>
            <label className="block text-meta uppercase tracking-wider text-ink-500 mb-1.5">
              Witness name
            </label>
            <input
              type="text"
              value={witnessName}
              onChange={(e) => setWitnessName(e.target.value)}
              placeholder="e.g. Dr Karim Hassan"
              className="w-full bg-white border border-surface-300 rounded-md px-3 py-2 text-sm text-ink-900 focus:outline-none focus:border-brand-600 focus:ring-1 focus:ring-brand-600/20"
            />
          </div>
          {error && (
            <div className="rounded-md border border-sev-critical/30 bg-sev-critical/5 p-2.5 text-sm text-sev-critical">
              {error}
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
            disabled={saving}
            className="px-4 py-2 text-sm font-medium bg-brand-600 hover:bg-brand-700 text-white rounded-md disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save consent"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Toggle({
  label,
  hint,
  value,
  onChange,
}: {
  label: string;
  hint?: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!value)}
      className="w-full flex items-start gap-3 text-left p-3 border border-surface-300 rounded-md hover:bg-surface-50"
    >
      <div
        className={`mt-0.5 w-9 h-5 rounded-full border transition shrink-0 relative ${
          value
            ? "bg-brand-600 border-brand-600"
            : "bg-surface-200 border-surface-300"
        }`}
        aria-pressed={value}
        role="switch"
      >
        <span
          className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow-soft transition ${
            value ? "left-[18px]" : "left-0.5"
          }`}
        />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-ink-900">{label}</div>
        {hint && (
          <div className="text-xs text-ink-600 mt-0.5">{hint}</div>
        )}
      </div>
    </button>
  );
}
