import { useState } from "react";
import type { Consent, Incident } from "../../lib/types";
import { Field } from "./Field";
import { ConsentModal } from "../case/ConsentModal";

interface MissingPersonDetails {
  name?: string;
  ageRange?: string;
  photoUrl?: string;
  lastSeenAt?: string;
  lastSeenLocation?: string;
  description?: string;
  status?: "open" | "found" | "deceased" | "closed";
}

const STATUS_STYLE: Record<string, string> = {
  open: "bg-sev-critical/10 text-sev-critical border-sev-critical/30",
  found: "bg-sev-low/10 text-sev-low border-sev-low/30",
  deceased: "bg-surface-200 text-ink-700 border-surface-300",
  closed: "bg-surface-200 text-ink-700 border-surface-300",
};

function fmtAt(iso?: string) {
  if (!iso) return undefined;
  return new Date(iso).toLocaleString();
}

function fmtTime(iso: string): string {
  return new Date(iso).toLocaleString([], {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function MissingPersonCard({ incident }: { incident: Incident }) {
  const d = incident.details as MissingPersonDetails;
  const consent = (incident.details.consent ?? null) as Consent | null;
  const [consentOpen, setConsentOpen] = useState(false);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        {d.photoUrl ? (
          <img
            src={d.photoUrl}
            alt=""
            className="w-16 h-16 rounded-lg bg-surface-200 object-cover border border-surface-200"
          />
        ) : (
          <div className="w-16 h-16 rounded-lg bg-surface-200 flex items-center justify-center text-2xl">
            👤
          </div>
        )}
        <div className="flex-1 min-w-0">
          <div className="font-display text-lg font-semibold text-ink-900 truncate">
            {d.name ?? "Unknown"}
          </div>
          <div className="text-meta text-ink-500">
            {d.ageRange ? `Age ~${d.ageRange}` : "Age unknown"}
          </div>
          {d.status && (
            <span
              className={`mt-1 inline-block text-meta px-1.5 py-0.5 rounded border font-medium uppercase tracking-wider ${
                STATUS_STYLE[d.status] ?? STATUS_STYLE.open
              }`}
            >
              {d.status}
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={() => setConsentOpen(true)}
          className="shrink-0 text-meta uppercase tracking-wider px-2 py-1 border border-surface-300 rounded-md text-ink-700 hover:bg-surface-100"
        >
          {consent ? "Edit consent" : "Capture consent"}
        </button>
      </div>

      {!consent && (
        <div className="rounded-md border border-sev-critical/30 bg-sev-critical/5 p-2.5 text-sm text-sev-critical">
          Consent not yet recorded — broadcasts blocked.
        </div>
      )}
      {consent && (
        <div className="rounded-md border border-sev-low/30 bg-sev-low/5 p-2.5 text-sm text-sev-low">
          Consent recorded by{" "}
          <span className="font-medium">{consent.witnessName}</span> ·{" "}
          <span className="font-mono">{fmtTime(consent.ts)}</span>
          <div className="text-meta text-ink-600 mt-1">
            {consent.publicBroadcast ? "✓" : "✗"} public broadcast ·{" "}
            {consent.referralSharing ? "✓" : "✗"} referral sharing ·{" "}
            {consent.dataStorage ? "✓" : "✗"} data storage
          </div>
        </div>
      )}

      <Field label="Last seen at" value={fmtAt(d.lastSeenAt)} />
      <Field label="Last seen location" value={d.lastSeenLocation} />
      <Field label="Description" value={d.description} />

      {consentOpen && (
        <ConsentModal
          incident={incident}
          onClose={() => setConsentOpen(false)}
        />
      )}
    </div>
  );
}
