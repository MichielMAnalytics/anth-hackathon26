import clsx from "clsx";
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
  open: "text-sev-critical",
  found: "text-sev-low",
  deceased: "text-ink-500",
};

function fmtAt(iso?: string) {
  if (!iso) return undefined;
  return new Date(iso).toLocaleString();
}

function initials(name?: string): string {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function MissingPersonCard({ incident }: { incident: Incident }) {
  const d = incident.details as MissingPersonDetails;
  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3.5">
        {d.photoUrl ? (
          <img
            src={d.photoUrl}
            alt=""
            className="w-14 h-14 rounded-sm bg-surface-200 object-cover border border-surface-300"
          />
        ) : (
          <div className="w-14 h-14 rounded-sm bg-surface-200 flex items-center justify-center font-mono text-[14px] font-semibold text-ink-700 tracking-[0.04em]">
            {initials(d.name)}
          </div>
        )}
        <div className="flex-1 min-w-0">
          <div className="font-display text-[16px] font-semibold text-ink-900 tracking-tighter truncate">
            {d.name ?? "Unknown"}
          </div>
          <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500 mt-0.5">
            {d.ageRange ? `Age ~${d.ageRange}` : "Age unknown"}
          </div>
          {d.status && (
            <div
              className={clsx(
                "mt-1.5 font-mono text-[10px] uppercase tracking-[0.14em] font-semibold",
                STATUS_STYLE[d.status] ?? STATUS_STYLE.open,
              )}
            >
              · {d.status}
            </div>
          )}
        </div>
      </div>

      <div className="space-y-4 pt-1">
        <Field label="Last seen at" value={fmtAt(d.lastSeenAt)} />
        <Field label="Last seen location" value={d.lastSeenLocation} />
        <Field label="Description" value={d.description} />
      </div>
    </div>
  );
}
