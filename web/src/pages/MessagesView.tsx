import { useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";
import { fetchDashboard } from "../lib/api";
import { useStore } from "../lib/store";
import { navigate } from "../lib/router";
import { AgentNowPlaying } from "../components/AgentNowPlaying";
import type { Dashboard } from "../lib/types";

const MAX_EVENTS = 60;

const REGION_LABELS: Record<string, string> = {
  sv8d: "Baghdad",
  sv3p: "Mosul",
  sy7q: "Aleppo",
  sv5t: "Damascus",
  s87w: "Sanaa",
  sv9j: "Beirut",
};

function regionLabel(prefix: string | null | undefined): string {
  if (!prefix) return "—";
  return REGION_LABELS[prefix] ?? prefix;
}

function fmtTime(iso: string | number) {
  const d = typeof iso === "number" ? new Date(iso) : new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function maskPhone(p?: string | null) {
  if (!p) return "—";
  if (p.length <= 4) return p;
  if (!/^[+0-9]/.test(p)) return p;
  return "···" + p.slice(-4);
}

type FeedEvent =
  | {
      kind: "message";
      key: string;
      ts: number;
      from: string;
      body: string;
      regionLabel: string;
      incidentId: string | null;
      distress: boolean;
    }
  | {
      kind: "thinking";
      key: string;
      ts: number;
      regionLabel: string;
      personName: string | null;
      incidentId: string | null;
    }
  | {
      kind: "decided";
      key: string;
      ts: number;
      regionLabel: string;
      narration: string;
      model: string | null;
      totalTurns: number;
      latencyMs: number;
      incidentId: string | null;
    };

export function MessagesView() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [events, setEvents] = useState<FeedEvent[]>([]);
  const seen = useRef<Set<string>>(new Set());
  const selectIncident = useStore((s) => s.selectIncident);

  // Initial seed: bring in recent distress messages so the feed isn't empty.
  useEffect(() => {
    let cancelled = false;
    fetchDashboard()
      .then((d) => {
        if (cancelled) return;
        setData(d);
        const seeded: FeedEvent[] = d.recentDistress.map((m) => ({
          kind: "message",
          key: `seed:${m.messageId}`,
          ts: new Date(m.ts).getTime(),
          from: m.from,
          body: m.body,
          regionLabel: m.regionLabel,
          incidentId: m.incidentId,
          distress: true,
        }));
        seeded.forEach((e) => seen.current.add(e.key));
        setEvents(seeded.sort((a, b) => b.ts - a.ts).slice(0, MAX_EVENTS));
      })
      .catch(() => {});
    const id = setInterval(() => {
      fetchDashboard().then((d) => !cancelled && setData(d)).catch(() => {});
    }, 15000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  // Live feed: own websocket. Keep generic so we can render multiple event kinds.
  useEffect(() => {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const url = `${proto}://${window.location.host}/ws/stream`;
    let ws: WebSocket | null = null;
    let closed = false;

    const push = (ev: FeedEvent) => {
      if (seen.current.has(ev.key)) return;
      seen.current.add(ev.key);
      setEvents((prev) => [ev, ...prev].slice(0, MAX_EVENTS));
    };

    const connect = () => {
      ws = new WebSocket(url);
      ws.onmessage = (raw) => {
        let msg: any;
        try {
          msg = JSON.parse(raw.data);
        } catch {
          return;
        }

        if (msg.type === "message" && msg.message) {
          const m = msg.message;
          const id = m.msg_id ?? m.messageId;
          if (!id) return;
          const ts = m.received_at ?? m.ts;
          const phone = m.sender_phone ?? m.from;
          const incidentId =
            msg.incident?.id ??
            m.in_reply_to_alert_id ??
            m.incidentId ??
            null;
          const region =
            msg.incident?.region ??
            (incidentId ? "—" : "—");
          push({
            kind: "message",
            key: `msg:${id}`,
            ts: ts ? new Date(ts).getTime() : Date.now(),
            from: phone ?? "—",
            body: m.body ?? "",
            regionLabel: region,
            incidentId,
            distress: false,
          });
        } else if (msg.type === "agent_thinking") {
          const aid = msg.alertId ?? msg.bucketKey ?? `t:${Date.now()}`;
          push({
            kind: "thinking",
            key: `think:${aid}:${Date.now()}`,
            ts: Date.now(),
            regionLabel: regionLabel(msg.regionPrefix),
            personName:
              msg.incident?.title ?? msg.incident?.personName ?? null,
            incidentId: msg.alertId ?? null,
          });
        } else if (msg.type === "decision_made") {
          const d = msg.decision ?? {};
          push({
            kind: "decided",
            key: `dec:${d.id ?? Date.now()}`,
            ts: Date.now(),
            regionLabel: regionLabel(msg.regionPrefix),
            narration:
              msg.narration ?? d.narration ?? d.summary ?? "Decision made",
            model: d.model ?? null,
            totalTurns: d.totalTurns ?? 0,
            latencyMs: d.latencyMs ?? 0,
            incidentId: msg.alertId ?? null,
          });
        }
      };
      ws.onclose = () => {
        if (!closed) window.setTimeout(connect, 1500);
      };
    };
    connect();

    return () => {
      closed = true;
      ws?.close();
    };
  }, []);

  const counts = useMemo(() => {
    let messages = 0;
    let distress = 0;
    let picks = 0;
    let decided = 0;
    for (const e of events) {
      if (e.kind === "message") {
        messages += 1;
        if (e.distress) distress += 1;
      } else if (e.kind === "thinking") {
        picks += 1;
      } else {
        decided += 1;
      }
    }
    return { messages, distress, picks, decided };
  }, [events]);

  return (
    <div className="h-full overflow-y-auto md:overflow-hidden md:grid md:grid-cols-[1fr_400px] min-h-0 bg-surface-100">
      <main className="px-4 sm:px-10 py-8 sm:py-12 md:overflow-y-auto">
        <div className="max-w-3xl mx-auto space-y-10">
          {/* Header */}
          <header className="grid grid-cols-1 lg:grid-cols-[1fr_auto] items-end gap-6">
            <div>
              <div className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-500">
                /// Live
              </div>
              <h1 className="font-display text-[40px] sm:text-[52px] leading-[1] font-semibold text-ink-900 tracking-tightest mt-3">
                Message stream.
              </h1>
              <p className="text-[14px] text-ink-500 mt-3 max-w-[58ch] leading-relaxed">
                Watch the wire come in. Every line is a civilian message — and
                every <span className="text-ink-900 font-medium">▸ pick</span> is
                the agent reading a bucket and deciding what to do next.
              </p>
            </div>
            <div className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-500 lg:text-right">
              <div>Window</div>
              <div className="text-ink-900 normal-case tracking-normal mt-1 text-[13px]">
                {data ? `last ${data.windowMinutes} min` : "live"}
              </div>
            </div>
          </header>

          {/* Counters — flat, vertical rules */}
          <div className="grid grid-cols-4 border-y border-surface-300">
            <Stat label="Messages" value={counts.messages} />
            <Stat
              label="Distress"
              value={counts.distress}
              tone="critical"
              divider
            />
            <Stat label="Agent picks" value={counts.picks} divider />
            <Stat label="Decisions" value={counts.decided} tone="ok" divider />
          </div>

          {/* Feed */}
          <section>
            <div className="flex items-baseline justify-between mb-4 pb-3 border-b border-surface-300">
              <div className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-500">
                /// Feed
              </div>
              <div className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-400 tabular-nums">
                {String(events.length).padStart(2, "0")} events
              </div>
            </div>

            {events.length === 0 ? (
              <div className="border border-dashed border-surface-300 rounded-md px-4 py-12 text-center">
                <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-400">
                  Quiet wire
                </div>
                <div className="text-[13px] text-ink-500 mt-1.5 max-w-[42ch] mx-auto">
                  Channel is open. New messages and agent activity will appear
                  here as they happen.
                </div>
              </div>
            ) : (
              <ol className="border-l border-surface-300 space-y-0">
                {events.map((e, i) => (
                  <li
                    key={e.key}
                    className="stagger-item"
                    style={{ ["--stagger-delay" as never]: `${Math.min(i, 6) * 25}ms` }}
                  >
                    {e.kind === "message" ? (
                      <MessageRow
                        ev={e}
                        onOpen={() => {
                          if (e.incidentId) {
                            selectIncident(e.incidentId);
                            navigate("cases");
                          }
                        }}
                      />
                    ) : e.kind === "thinking" ? (
                      <ThinkingRow ev={e} />
                    ) : (
                      <DecidedRow ev={e} />
                    )}
                  </li>
                ))}
              </ol>
            )}
          </section>

          <footer className="pt-6 border-t border-surface-300 flex items-center justify-between font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-400">
            <span>SafeThread · Live wire</span>
            <span className="normal-case tracking-normal">
              {events.length} recent · streaming
            </span>
          </footer>
        </div>
      </main>

      {/* Right rail — pinned now-playing widget */}
      <aside className="md:border-l border-t md:border-t-0 border-surface-300 bg-white md:overflow-y-auto md:max-h-full">
        <div className="px-6 py-8 sm:py-10 space-y-5">
          <div>
            <div className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-500">
              /// Now playing
            </div>
            <h2 className="font-display text-[22px] leading-tight font-semibold text-ink-900 tracking-tighter mt-2">
              Agent at work
            </h2>
            <p className="text-[12.5px] text-ink-500 mt-1.5 leading-snug">
              The matching engine, in real time. Watch it pick a bucket, read
              the messages, and decide.
            </p>
          </div>
          <AgentNowPlaying />

          <div className="pt-4 border-t border-surface-300">
            <div className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-500">
              /// How it works
            </div>
            <h3 className="font-display text-[16px] leading-tight font-semibold text-ink-900 tracking-tighter mt-2">
              From message to decision
            </h3>
          </div>
          <ol className="space-y-3">
            <Step
              n={1}
              dot="bg-ink-400"
              title="Wire receives a message"
              body="A civilian SMS lands and is geo-bucketed by region."
            />
            <Step
              n={2}
              dot="bg-brand-600"
              title="Agent reads the bucket"
              body="When activity crosses a threshold, the agent claims the bucket and runs a multi-turn loop."
            />
            <Step
              n={3}
              dot="bg-sev-low"
              title="Decision lands"
              body="It either stands by, queues a suggestion, or — with approval — sends a broadcast."
            />
          </ol>
        </div>
      </aside>
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
  divider,
}: {
  label: string;
  value: number;
  tone?: "critical" | "high" | "ok";
  divider?: boolean;
}) {
  const color =
    tone === "critical"
      ? "text-sev-critical"
      : tone === "high"
        ? "text-sev-high"
        : tone === "ok"
          ? "text-sev-low"
          : "text-ink-900";
  return (
    <div className={`px-4 sm:px-6 py-5 ${divider ? "border-l border-surface-300" : ""}`}>
      <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">
        {label}
      </div>
      <div
        className={`font-display text-[28px] sm:text-[36px] leading-none tracking-tightest mt-2 tabular-nums ${color}`}
      >
        {value}
      </div>
    </div>
  );
}

function Bullet({ className }: { className: string }) {
  return (
    <span
      aria-hidden
      className={clsx(
        "absolute -left-[5px] top-3 w-2 h-2 rounded-full ring-4 ring-surface-100",
        className,
      )}
    />
  );
}

function MessageRow({
  ev,
  onOpen,
}: {
  ev: Extract<FeedEvent, { kind: "message" }>;
  onOpen: () => void;
}) {
  return (
    <button
      onClick={onOpen}
      disabled={!ev.incidentId}
      className="group relative w-full text-left pl-5 pr-3 py-4 border-b border-surface-300 hover:bg-white transition disabled:cursor-default"
    >
      <Bullet className={ev.distress ? "bg-sev-critical" : "bg-ink-400"} />
      <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">
        <span className="text-ink-900">{maskPhone(ev.from)}</span>
        <span className="text-surface-400">·</span>
        <span>{ev.regionLabel}</span>
        {ev.distress && (
          <span className="ml-1 px-1.5 py-[1px] rounded bg-sev-critical/10 text-sev-critical font-mono text-[9px] tracking-[0.14em]">
            distress
          </span>
        )}
        <span className="ml-auto text-ink-400 normal-case tracking-normal tabular-nums">
          {fmtTime(ev.ts)}
        </span>
      </div>
      <div className="mt-1.5 text-[13px] text-ink-900 leading-snug line-clamp-2">
        {ev.body}
      </div>
    </button>
  );
}

function ThinkingRow({
  ev,
}: {
  ev: Extract<FeedEvent, { kind: "thinking" }>;
}) {
  return (
    <div className="relative pl-5 pr-3 py-3 border-b border-surface-300 bg-brand-600/[0.03]">
      <Bullet className="bg-brand-600 animate-pulse-dot" />
      <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.14em]">
        <span className="text-brand-600">Agent · thinking</span>
        <span className="text-surface-400">·</span>
        <span className="text-ink-700">{ev.regionLabel}</span>
        <span className="ml-auto text-ink-400 normal-case tracking-normal tabular-nums">
          {fmtTime(ev.ts)}
        </span>
      </div>
      <div className="mt-1.5 text-[13px] text-ink-900 leading-snug">
        Reading the bucket
        {ev.personName ? (
          <>
            {" "}— <span className="font-medium">{ev.personName}</span>
          </>
        ) : null}
        …
      </div>
    </div>
  );
}

function DecidedRow({
  ev,
}: {
  ev: Extract<FeedEvent, { kind: "decided" }>;
}) {
  return (
    <div className="relative pl-5 pr-3 py-3 border-b border-surface-300">
      <Bullet className="bg-sev-low" />
      <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.14em]">
        <span className="text-sev-low">Agent · decided</span>
        <span className="text-surface-400">·</span>
        <span className="text-ink-700">{ev.regionLabel}</span>
        <span className="ml-auto text-ink-400 normal-case tracking-normal tabular-nums">
          {fmtTime(ev.ts)}
        </span>
      </div>
      <div className="mt-1.5 text-[13px] text-ink-900 leading-snug">
        {ev.narration}
      </div>
      <div className="mt-1.5 flex items-center gap-3 font-mono text-[10px] text-ink-400 tabular-nums">
        {ev.model ? <span>{ev.model}</span> : null}
        <span>
          {ev.totalTurns} turn{ev.totalTurns === 1 ? "" : "s"}
        </span>
        <span>{(ev.latencyMs / 1000).toFixed(1)}s</span>
      </div>
    </div>
  );
}

function Step({
  n,
  dot,
  title,
  body,
}: {
  n: number;
  dot: string;
  title: string;
  body: string;
}) {
  return (
    <li className="flex gap-3">
      <div className="shrink-0 mt-0.5 flex flex-col items-center">
        <span className={clsx("w-2 h-2 rounded-full", dot)} />
      </div>
      <div className="flex-1">
        <div className="font-mono text-[9.5px] uppercase tracking-[0.14em] text-ink-400">
          Step {String(n).padStart(2, "0")}
        </div>
        <div className="text-[13px] text-ink-900 font-medium tracking-tight mt-0.5">
          {title}
        </div>
        <div className="text-[12px] text-ink-500 leading-snug mt-0.5">
          {body}
        </div>
      </div>
    </li>
  );
}
