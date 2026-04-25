export type Category =
  | "missing_person"
  | "resource_shortage"
  | "medical"
  | "safety"
  | "other";

export type Severity = "low" | "medium" | "high" | "critical";

export interface Extracted {
  personRef?: string;
  location?: string;
  distress?: boolean;
  needs?: string[];
}

export interface Message {
  messageId: string;
  incidentId: string;
  from: string;
  body: string;
  ts: string;
  geohash?: string | null;
  extracted?: Extracted | null;
}

export interface Incident {
  id: string;
  category: Category;
  title: string;
  severity: Severity;
  details: Record<string, unknown>;
  messageCount: number;
  lastActivity: string | null;
}

export interface StreamEvent {
  type: "message" | "incident_upserted";
  incident: Incident;
  message: Message | null;
}
