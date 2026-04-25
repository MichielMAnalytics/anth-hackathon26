import type { Incident } from "../../lib/types";
import { Field } from "./Field";

interface ResourceShortageDetails {
  resource?: string;
  location?: string;
  reporterCount?: number;
  severity?: string;
}

const ICON: Record<string, string> = {
  water: "💧",
  food: "🍞",
  shelter: "🏠",
  power: "⚡",
};

export function ResourceShortageCard({ incident }: { incident: Incident }) {
  const d = incident.details as ResourceShortageDetails;
  const icon = d.resource ? (ICON[d.resource] ?? "📦") : "📦";
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="w-16 h-16 rounded-lg bg-paper-200 flex items-center justify-center text-3xl">
          {icon}
        </div>
        <div>
          <div className="text-meta uppercase tracking-wider text-paper-500">
            Resource shortage
          </div>
          <div className="font-display text-lg text-paper-900 capitalize">
            {d.resource ?? "—"}
          </div>
        </div>
      </div>
      <Field label="Location" value={d.location} />
      <Field
        label="Reporters"
        value={
          d.reporterCount !== undefined
            ? `${d.reporterCount} citizen reports`
            : undefined
        }
      />
    </div>
  );
}
