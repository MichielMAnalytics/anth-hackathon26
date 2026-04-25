import type { Incident } from "../../lib/types";
import { GenericCard } from "./GenericCard";
import { MedicalCard } from "./MedicalCard";
import { MissingPersonCard } from "./MissingPersonCard";
import { ResourceShortageCard } from "./ResourceShortageCard";
import { SafetyCard } from "./SafetyCard";

export function DetailPanel({ incident }: { incident: Incident }) {
  switch (incident.category) {
    case "missing_person":
      return <MissingPersonCard incident={incident} />;
    case "resource_shortage":
      return <ResourceShortageCard incident={incident} />;
    case "medical":
      return <MedicalCard incident={incident} />;
    case "safety":
      return <SafetyCard incident={incident} />;
    default:
      return <GenericCard incident={incident} />;
  }
}
