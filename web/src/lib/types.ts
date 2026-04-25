export type Category =
  | "missing_person"
  | "resource_shortage"
  | "medical"
  | "safety"
  | "other";

export type Severity = "low" | "medium" | "high" | "critical";

export type Region =
  | "IRQ_BAGHDAD"
  | "IRQ_MOSUL"
  | "SYR_ALEPPO"
  | "SYR_DAMASCUS"
  | "YEM_SANAA"
  | "LBN_BEIRUT";

export type Channel = "app" | "sms" | "fallback";

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
  lat?: number | null;
  lon?: number | null;
  extracted?: Extracted | null;
  outbound?: boolean;
  via?: string | null;
}

export interface Incident {
  id: string;
  category: Category;
  title: string;
  severity: Severity;
  region: Region;
  lat?: number | null;
  lon?: number | null;
  details: Record<string, unknown>;
  messageCount: number;
  lastActivity: string | null;
}

export interface StreamEvent {
  type: "message" | "incident_upserted";
  incident: Incident;
  message: Message | null;
}

export interface Audience {
  id: string;
  label: string;
  description: string;
  count: number;
  regions: Region[];
  roles: string[];
  channelsAvailable: Channel[];
}

export interface RegionStats {
  region: Region;
  label: string;
  lat: number;
  lon: number;
  reachable: number;
  incidentCount: number;
  messageCount: number;
  msgsPerMin: number;
  baselineMsgsPerMin: number;
  anomaly: boolean;
}

export interface BroadcastAck {
  ok: boolean;
  queued: number;
  batches: number;
  etaSeconds: number;
  channels: string[];
  audienceLabel: string;
  note: string;
}

export type SendMode = "alert" | "request";

export interface TimelineBucket {
  ts: string;
  count: number;
}

export interface RegionTimeline {
  region: Region;
  minutes: number;
  bucketSeconds: number;
  buckets: TimelineBucket[];
  total: number;
}
