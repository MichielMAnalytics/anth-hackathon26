import { authHeaders } from "./auth";
import type {
  Audience,
  BroadcastAck,
  Channel,
  Dashboard,
  Incident,
  Message,
  Operator,
  Region,
  RegionStats,
  RegionTimeline,
  SendMode,
  StreamEvent,
} from "./types";

function ah(extra: Record<string, string> = {}): Record<string, string> {
  return { ...authHeaders(), ...extra };
}

export async function fetchIncidents(): Promise<Incident[]> {
  const r = await fetch("/api/incidents", { headers: ah() });
  if (!r.ok) throw new Error("incidents");
  return r.json();
}

export async function fetchMessages(incidentId: string): Promise<Message[]> {
  const r = await fetch(`/api/incidents/${incidentId}/messages`, { headers: ah() });
  if (!r.ok) throw new Error("messages");
  return r.json();
}

export async function fetchAudiences(): Promise<Audience[]> {
  const r = await fetch("/api/audiences", { headers: ah() });
  if (!r.ok) throw new Error("audiences");
  return r.json();
}

export async function fetchRegionStats(): Promise<RegionStats[]> {
  const r = await fetch("/api/regions/stats", { headers: ah() });
  if (!r.ok) throw new Error("regions");
  return r.json();
}

export async function fetchDashboard(): Promise<Dashboard> {
  const r = await fetch("/api/dashboard", { headers: ah() });
  if (!r.ok) throw new Error("dashboard");
  return r.json();
}

export async function fetchMe(): Promise<Operator> {
  const r = await fetch("/api/me", { headers: ah() });
  if (!r.ok) throw new Error("me");
  return r.json();
}

export async function fetchOperators(): Promise<Operator[]> {
  const r = await fetch("/api/operators");
  if (!r.ok) throw new Error("operators");
  return r.json();
}

export async function fetchRegionTimeline(
  region: Region,
  minutes = 60,
  bucketSeconds = 60,
): Promise<RegionTimeline> {
  const r = await fetch(
    `/api/regions/${region}/timeline?minutes=${minutes}&bucket=${bucketSeconds}`,
    { headers: ah() },
  );
  if (!r.ok) throw new Error("timeline");
  return r.json();
}

export async function seedDemo(): Promise<void> {
  await fetch("/api/sim/seed", { method: "POST" });
}

export async function sendBroadcast(
  mode: SendMode,
  payload: {
    incidentId?: string;
    audienceId: string;
    channels: Channel;
    region?: Region | null;
    body: string;
    attachments?: Record<string, unknown>;
  },
): Promise<BroadcastAck> {
  const path = mode === "alert" ? "/api/alerts" : "/api/requests";
  const r = await fetch(path, {
    method: "POST",
    headers: ah({ "content-type": "application/json" }),
    body: JSON.stringify({ attachments: {}, ...payload }),
  });
  return r.json();
}

export async function sendCaseMessage(
  incidentId: string,
  body: string,
  via: Channel,
  audienceId?: string,
): Promise<{ ok: boolean; broadcast?: BroadcastAck | null }> {
  const r = await fetch(`/api/cases/${incidentId}/messages`, {
    method: "POST",
    headers: ah({ "content-type": "application/json" }),
    body: JSON.stringify({ body, via, audienceId }),
  });
  return r.json();
}

export function openStream(onEvent: (e: StreamEvent) => void) {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const url = `${proto}://${window.location.host}/ws/stream`;
  let ws: WebSocket | null = null;
  let closed = false;

  const connect = () => {
    ws = new WebSocket(url);
    ws.onmessage = (ev) => {
      try {
        onEvent(JSON.parse(ev.data));
      } catch {
        /* ignore */
      }
    };
    ws.onclose = () => {
      if (!closed) setTimeout(connect, 1500);
    };
  };
  connect();
  return () => {
    closed = true;
    ws?.close();
  };
}
