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
  open: "bg-sev-critical/15 text-sev-critical border-sev-critical/30",
  found: "bg-sev-low/15 text-sev-low border-sev-low/30",
  deceased: "bg-ink-700 text-ink-300 border-ink-600",
};

function fmtAt(iso?: string) {
  if (!iso) return undefined;
  const d = new Date(iso);
  return d.toLocaleString();
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
            className="w-16 h-16 rounded-lg bg-ink-800 object-cover"
          />
        ) : (
          <div className="w-16 h-16 rounded-lg bg-ink-800 flex items-center justify-center text-2xl">
            👤
          </div>
        )}
        <div className="flex-1 min-w-0">
          <div className="text-base font-semibold text-ink-100 truncate">
            {d.name ?? "Unknown"}
          </div>
          <div className="text-xs text-ink-400">
            {d.ageRange ? `Age ~${d.ageRange}` : "Age unknown"}
          </div>
          {d.status && (
            <span
              className={`mt-1 inline-block text-[10px] px-1.5 py-0.5 rounded border font-mono uppercase tracking-wider ${
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
