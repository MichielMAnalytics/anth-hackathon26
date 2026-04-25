import type {
  Audience,
  BroadcastAck,
  Channel,
  Incident,
  Message,
  Region,
  RegionStats,
  SendMode,
  StreamEvent,
} from "./types";

export async function fetchIncidents(): Promise<Incident[]> {
  const r = await fetch("/api/incidents");
  if (!r.ok) throw new Error("incidents");
  return r.json();
}

export async function fetchMessages(incidentId: string): Promise<Message[]> {
  const r = await fetch(`/api/incidents/${incidentId}/messages`);
  if (!r.ok) throw new Error("messages");
  return r.json();
}

export async function fetchAudiences(): Promise<Audience[]> {
  const r = await fetch("/api/audiences");
  if (!r.ok) throw new Error("audiences");
  return r.json();
}

export async function fetchRegionStats(): Promise<RegionStats[]> {
  const r = await fetch("/api/regions/stats");
  if (!r.ok) throw new Error("regions");
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
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ attachments: {}, ...payload }),
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
