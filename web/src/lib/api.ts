import type { Incident, Message } from "./types";

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

export async function seedDemo(): Promise<void> {
  await fetch("/api/sim/seed", { method: "POST" });
}

export async function sendAlert(payload: {
  incidentId: string;
  name: string;
  photoUrl?: string;
  lastSeenLocation?: string;
  description?: string;
}): Promise<void> {
  await fetch("/api/alerts", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function openStream(onEvent: (e: import("./types").StreamEvent) => void) {
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
