import type { Incident } from "../../lib/types";
import { Field } from "./Field";

interface SafetyDetails {
  threat?: string;
  location?: string;
  ongoing?: boolean;
}

export function SafetyCard({ incident }: { incident: Incident }) {
  const d = incident.details as SafetyDetails;
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="w-16 h-16 rounded-lg bg-surface-200 flex items-center justify-center text-3xl">
          ⚠
        </div>
        <div>
          <div className="text-meta uppercase tracking-wider text-ink-500">
            Safety
          </div>
          <div className="font-display text-lg font-semibold text-ink-900">
            {d.ongoing ? "Ongoing threat" : "Threat resolved / static"}
          </div>
        </div>
      </div>
      <Field label="Threat" value={d.threat} />
      <Field label="Location" value={d.location} />
    </div>
  );
}
