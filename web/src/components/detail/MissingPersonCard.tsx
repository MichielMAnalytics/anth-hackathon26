import type { Incident } from "../../lib/types";
import { Field } from "./Field";

interface MissingPersonDetails {
  name?: string;
  ageRange?: string;
  photoUrl?: string;
  lastSeenAt?: string;
  lastSeenLocation?: string;
  description?: string;
  status?: "open" | "found" | "deceased";
}

const STATUS_STYLE: Record<string, string> = {
  open: "bg-sev-critical/10 text-sev-critical border-sev-critical/30",
  found: "bg-sev-low/10 text-sev-low border-sev-low/30",
  deceased: "bg-paper-200 text-paper-700 border-paper-300",
};

function fmtAt(iso?: string) {
  if (!iso) return undefined;
  return new Date(iso).toLocaleString();
}

export function MissingPersonCard({ incident }: { incident: Incident }) {
  const d = incident.details as MissingPersonDetails;
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        {d.photoUrl ? (
          <img
            src={d.photoUrl}
            alt=""
            className="w-16 h-16 rounded-lg bg-paper-200 object-cover border border-paper-200"
          />
        ) : (
          <div className="w-16 h-16 rounded-lg bg-paper-200 flex items-center justify-center text-2xl">
            👤
          </div>
        )}
        <div className="flex-1 min-w-0">
          <div className="font-display text-lg text-paper-900 truncate">
            {d.name ?? "Unknown"}
          </div>
          <div className="text-meta text-paper-500">
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
      </div>

      <Field label="Last seen at" value={fmtAt(d.lastSeenAt)} />
      <Field label="Last seen location" value={d.lastSeenLocation} />
      <Field label="Description" value={d.description} />
    </div>
  );
}
