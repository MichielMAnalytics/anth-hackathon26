import type { Incident } from "../../lib/types";
import { Field } from "./Field";

interface MedicalDetails {
  condition?: string;
  medicationNeeded?: string;
  location?: string;
  patientName?: string;
  urgency?: string;
}

export function MedicalCard({ incident }: { incident: Incident }) {
  const d = incident.details as MedicalDetails;
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="w-16 h-16 rounded-lg bg-paper-200 flex items-center justify-center text-3xl">
          ⚕
        </div>
        <div>
          <div className="text-meta uppercase tracking-wider text-paper-500">
            Medical request
          </div>
          <div className="font-display text-lg text-paper-900">
            {d.patientName ?? "Patient unknown"}
          </div>
        </div>
      </div>
      <Field label="Condition" value={d.condition} />
      <Field label="Medication needed" value={d.medicationNeeded} />
      <Field label="Location" value={d.location} />
      <Field label="Urgency" value={d.urgency} />
    </div>
  );
}
