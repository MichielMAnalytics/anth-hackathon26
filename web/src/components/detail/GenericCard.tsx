import type { Incident } from "../../lib/types";
import { Field } from "./Field";

export function GenericCard({ incident }: { incident: Incident }) {
  const summary =
    typeof incident.details["summary"] === "string"
      ? (incident.details["summary"] as string)
      : undefined;
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="w-16 h-16 rounded-lg bg-ink-800 flex items-center justify-center text-3xl">
          •
        </div>
        <div>
          <div className="text-xs uppercase tracking-wider text-ink-500">
            {incident.category}
          </div>
          <div className="text-base font-semibold text-ink-100">
            {incident.title}
          </div>
        </div>
      </div>
      <Field label="Summary" value={summary} />
      <pre className="mt-2 text-[11px] font-mono bg-ink-900 border border-ink-800 rounded p-3 overflow-x-auto text-ink-300">
        {JSON.stringify(incident.details, null, 2)}
      </pre>
    </div>
  );
}
