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
        <div className="w-16 h-16 rounded-lg bg-paper-200 flex items-center justify-center text-3xl text-paper-700">
          •
        </div>
        <div>
          <div className="text-meta uppercase tracking-wider text-paper-500">
            {incident.category}
          </div>
          <div className="font-display text-lg text-paper-900">
            {incident.title}
          </div>
        </div>
      </div>
      <Field label="Summary" value={summary} />
      <pre className="mt-2 text-meta font-mono bg-paper-100 border border-paper-200 rounded p-3 overflow-x-auto text-paper-700">
        {JSON.stringify(incident.details, null, 2)}
      </pre>
    </div>
  );
}
