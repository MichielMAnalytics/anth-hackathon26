import { useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";
import { fetchDashboard } from "../lib/api";
import { useStore } from "../lib/store";
import { navigate } from "../lib/router";
import { AgentNowPlaying } from "../components/AgentNowPlaying";
import { CreateCaseModal } from "../components/CreateCaseModal";
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
      triage: {
        classification: string;
        confidence: number | null;
        geohash6: string | null;
        language: string | null;
      } | null;
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
      toolCalls: { id: string; name: string; mode: string; approvalStatus?: string | null }[];
    };

interface ToolMeta {
  label: string;
  blurb: string;
  classes: string; // tailwind classes for chip background + text
}

const TOOL_META: Record<string, ToolMeta> = {
  send: {
    label: "Send broadcast",
    blurb: "Pushes an SMS or in-app message to one person, a group, or a region.",
    classes: "bg-brand-600/10 text-brand-600 border-brand-600/20",
  },
  record_sighting: {
    label: "Record sighting",
    blurb: "Logs a witness report (location + observer + confidence) against the case.",
    classes: "bg-violet-100 text-violet-700 border-violet-200",
  },
  upsert_cluster: {
    label: "Update cluster",
    blurb: "Groups nearby sightings into a named cluster of activity.",
    classes: "bg-amber-100 text-amber-700 border-amber-200",
  },
  merge_clusters: {
    label: "Merge clusters",
    blurb: "Collapses overlapping clusters into one.",
    classes: "bg-amber-100 text-amber-700 border-amber-200",
  },
  upsert_trajectory: {
    label: "Update trajectory",
    blurb: "Connects clusters into a likely path of movement.",
    classes: "bg-amber-100 text-amber-700 border-amber-200",
  },
  apply_tag: {
    label: "Apply tag",
    blurb: "Adds a structured tag (e.g. medical, evacuated) to the case.",
    classes: "bg-sky-100 text-sky-700 border-sky-200",
  },
  remove_tag: {
    label: "Remove tag",
    blurb: "Removes a tag previously applied to the case.",
    classes: "bg-sky-100 text-sky-700 border-sky-200",
  },
  categorize_alert: {
    label: "Categorize alert",
    blurb: "Suggests the case category (medical, missing person, etc).",
    classes: "bg-sky-100 text-sky-700 border-sky-200",
  },
  escalate_to_ngo: {
    label: "Escalate",
    blurb: "Pushes the case up to a senior operator for human review.",
    classes: "bg-sev-critical/10 text-sev-critical border-sev-critical/20",
  },
  mark_bad_actor: {
    label: "Flag bad actor",
    blurb: "Marks a sender as suspicious — quarantines their inputs.",
    classes: "bg-sev-critical/10 text-sev-critical border-sev-critical/20",
  },
  update_alert_status: {
    label: "Update status",
    blurb: "Changes the case status (open / resolved / archived).",
    classes: "bg-ink-100 text-ink-700 border-ink-200",
  },
  noop: {
    label: "Stand by",
    blurb: "No action needed — the agent decides to wait.",
    classes: "bg-surface-200 text-ink-500 border-surface-300",
  },
};

function toolMeta(name: string): ToolMeta {
  return (
    TOOL_META[name] ?? {
      label: name,
      blurb: "Tool call.",
      classes: "bg-surface-200 text-ink-700 border-surface-300",
    }
  );
}

export function MessagesView() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [events, setEvents] = useState<FeedEvent[]>([]);
  const seen = useRef<Set<string>>(new Set());
  const selectIncident = useStore((s) => s.selectIncident);
  const [makeCaseFromMsg, setMakeCaseFromMsg] = useState<
    Extract<FeedEvent, { kind: "message" }> | null
  >(null);

  type MessageEvent = Extract<FeedEvent, { kind: "message" }>;

  // Compute co-mention matches across orphan messages: tokens (length ≥4,
  // not stop words) that appear in body text of at least 2 different
  // orphan messages. Two messages saying "Maryam" both light up.
  const coMentionMatchesByKey = useMemo(() => {
    const STOP = new Set([
      "alert", "hello", "hellp", "please", "help", "from", "info",
      "with", "this", "that", "have", "been", "they", "them", "miss",
      "missing", "about", "your", "thanks", "where", "when", "what",
      "near", "here", "there",
    ]);
    const tokensByKey = new Map<string, Set<string>>();
    for (const e of events) {
      if (e.kind !== "message") continue;
      if (e.incidentId) continue; // only orphans participate
      const matches = e.body.toLowerCase().match(/[\p{L}]{4,}/gu) ?? [];
      const tokens = new Set<string>();
      for (const m of matches) if (!STOP.has(m)) tokens.add(m);
      tokensByKey.set(e.key, tokens);
    }
    const counts = new Map<string, number>();
    for (const tokens of tokensByKey.values()) {
      for (const t of tokens) counts.set(t, (counts.get(t) ?? 0) + 1);
    }
    const out = new Map<string, Set<string>>();
    for (const [key, tokens] of tokensByKey) {
      const matched = new Set<string>();
      for (const t of tokens) if ((counts.get(t) ?? 0) >= 2) matched.add(t);
      out.set(key, matched);
    }
    return out;
  }, [events]);

  // The right-rail workspace: the curated set of messages an operator
  // should review. Same trigger as the inline "Make a case" button —
  // sighting-classified, OR co-mentioned with another orphan, AND not
  // already a case. Then group by co-mention token (e.g. "maryam") so
  // 5 messages about the same person collapse into a single entry.
  const caseSuggestions = useMemo(() => {
    type Group = {
      kind: "group";
      token: string;
      events: MessageEvent[];
      latestTs: number;
    };
    type Solo = { kind: "solo"; ev: MessageEvent };
    type Suggestion = Group | Solo;

    const groups = new Map<string, Group>();
    const solos: Solo[] = [];

    for (const e of events) {
      if (e.kind !== "message") continue;
      if (e.incidentId) continue;
      const c = e.triage?.classification ?? "";
      if (c === "noise" || c === "bad_actor") continue;
      const matches = coMentionMatchesByKey.get(e.key) ?? new Set<string>();
      const hasCoMention = matches.size > 0;
      const isSighting = c === "sighting";
      if (!isSighting && !hasCoMention) continue;
      if (hasCoMention) {
        const primary = [...matches].sort()[0];
        const existing = groups.get(primary);
        if (existing) {
          existing.events.push(e);
          existing.latestTs = Math.max(existing.latestTs, e.ts);
        } else {
          groups.set(primary, {
            kind: "group",
            token: primary,
            events: [e],
            latestTs: e.ts,
          });
        }
      } else {
        solos.push({ kind: "solo", ev: e });
      }
    }

    const list: Suggestion[] = [...groups.values(), ...solos];
    list.sort((a, b) => {
      const at = a.kind === "group" ? a.latestTs : a.ev.ts;
      const bt = b.kind === "group" ? b.latestTs : b.ev.ts;
      return bt - at;
    });
    return list;
  }, [events, coMentionMatchesByKey]);

  // Initial seed: bring in recent distress messages so the feed isn't empty.
  useEffect(() => {
    let cancelled = false;
    fetchDashboard()
      .then((d) => {
        if (cancelled) return;
        setData(d);
        const seeded: FeedEvent[] = d.recentDistress.map((m) => ({
          kind: "message",
          key: `msg:${m.messageId}`,
          ts: new Date(m.ts).getTime(),
          from: m.from,
          body: m.body,
          regionLabel: m.regionLabel,
          incidentId: m.incidentId,
          distress: true,
          triage: m.triage ?? null,
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
      if (seen.current.has(ev.key)) {
        // Upsert: a second arrival of the same message (e.g. once with
        // raw body, once enriched with triage) should overwrite the
        // existing entry rather than be dropped, so the classification
        // pill can appear after triage finishes.
        if (ev.kind === "message") {
          setEvents((prev) =>
            prev.map((existing) => (existing.key === ev.key ? ev : existing)),
          );
        }
        return;
      }
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
            triage: m.triage ?? null,
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
          const calls = Array.isArray(d.toolCalls) ? d.toolCalls : [];
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
            toolCalls: calls.map((c: any) => ({
              id: c.id,
              name: c.name,
              mode: c.mode,
              approvalStatus: c.approvalStatus ?? null,
            })),
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
                        onMakeCase={() => setMakeCaseFromMsg(e)}
                        coMentionMatches={
                          coMentionMatchesByKey.get(e.key) ?? new Set()
                        }
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

      {/* Right rail — needs-review workspace + collapsible context */}
      <aside className="md:border-l border-t md:border-t-0 border-surface-300 bg-white md:overflow-y-auto md:max-h-full">
        <div className="px-6 py-8 sm:py-10 space-y-6">
          {/* PRIMARY: needs review */}
          <div>
            <div className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-500">
              /// Needs review
            </div>
            <h2 className="font-display text-[22px] leading-tight font-semibold text-ink-900 tracking-tighter mt-2">
              Suggested cases
            </h2>
            <p className="text-[12.5px] text-ink-500 mt-1.5 leading-snug">
              Civilian messages worth a caseworker's attention. Click to open
              and refine into a case.
            </p>
          </div>
          {caseSuggestions.length === 0 ? (
            <div className="rounded border border-dashed border-surface-300 px-4 py-6 text-center">
              <div className="text-[12px] text-ink-500">
                Nothing to review.
              </div>
              <div className="text-[10.5px] text-ink-400 mt-1">
                Suggestions appear here as messages come in.
              </div>
            </div>
          ) : (
            <ul className="space-y-2">
              {caseSuggestions.map((s) => {
                const top =
                  s.kind === "group"
                    ? s.events.sort((a, b) => b.ts - a.ts)[0]
                    : s.ev;
                return (
                  <li key={s.kind === "group" ? `g:${s.token}` : s.ev.key}>
                    <button
                      type="button"
                      onClick={() => setMakeCaseFromMsg(top)}
                      className="w-full text-left rounded border border-surface-300 hover:border-ink-400 hover:bg-surface-50 transition px-3 py-2.5"
                    >
                      <div className="flex items-center gap-2">
                        {s.kind === "group" ? (
                          <span className="font-mono text-[11px] font-semibold text-ink-900 truncate">
                            {s.token}
                          </span>
                        ) : (
                          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">
                            {top.triage?.classification ?? "signal"}
                          </span>
                        )}
                        {s.kind === "group" && (
                          <span className="font-mono text-[9.5px] uppercase tracking-[0.14em] px-1.5 py-[1px] rounded bg-ink-900 text-white">
                            {s.events.length} msgs
                          </span>
                        )}
                        <span className="ml-auto font-mono text-[10px] tabular-nums text-ink-400">
                          {fmtTime(top.ts)}
                        </span>
                      </div>
                      <div className="mt-1.5 text-[12.5px] text-ink-900 leading-snug line-clamp-2">
                        {top.body}
                      </div>
                      <div className="mt-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">
                        → make a case
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}

          {/* SECONDARY: now playing */}
          <details className="pt-3 border-t border-surface-300 group">
            <summary className="cursor-pointer list-none flex items-center gap-2 select-none">
              <Chevron />
              <div className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-500">
                /// Now playing
              </div>
            </summary>
            <div className="mt-3 space-y-3">
              <p className="text-[12px] text-ink-500 leading-snug">
                The matching engine, in real time. Watch it pick a bucket, read
                the messages, and decide.
              </p>
              <AgentNowPlaying />
            </div>
          </details>

          {/* TERTIARY: agent capabilities legend */}
          <details className="pt-3 border-t border-surface-300">
            <summary className="cursor-pointer list-none flex items-center gap-2 select-none">
              <Chevron />
              <div className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-500">
                /// What the agent can do
              </div>
            </summary>
            <div className="mt-3 space-y-3">
              <p className="text-[12px] text-ink-500 leading-snug">
                Solid chip = executed automatically. Dashed = staged as a
                suggestion, waiting on a human.
              </p>
              <ul className="space-y-2.5">
                {[
                  "send",
                  "record_sighting",
                  "upsert_cluster",
                  "merge_clusters",
                  "upsert_trajectory",
                  "apply_tag",
                  "categorize_alert",
                  "escalate_to_ngo",
                  "mark_bad_actor",
                  "update_alert_status",
                  "noop",
                ].map((name) => {
                  const m = toolMeta(name);
                  return (
                    <li key={name} className="flex items-start gap-2.5">
                      <span
                        className={clsx(
                          "shrink-0 mt-[2px] inline-flex items-center px-2 py-[3px] rounded-md border font-mono text-[10px] uppercase tracking-[0.14em] font-medium",
                          m.classes,
                        )}
                      >
                        {m.label}
                      </span>
                      <span className="text-[12px] text-ink-500 leading-snug">
                        {m.blurb}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>
          </details>
        </div>
      </aside>

      {makeCaseFromMsg && (
        <CreateCaseModal
          onClose={() => setMakeCaseFromMsg(null)}
          defaults={{ description: makeCaseFromMsg.body }}
          onCreated={() => navigate("cases")}
        />
      )}
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

function Chevron() {
  return (
    <svg
      width="9"
      height="9"
      viewBox="0 0 10 10"
      fill="none"
      className="text-ink-500 transition-transform group-open:rotate-90"
    >
      <path
        d="M3.5 1.5L7 5L3.5 8.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
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
  onMakeCase,
  coMentionMatches,
}: {
  ev: Extract<FeedEvent, { kind: "message" }>;
  onOpen: () => void;
  onMakeCase: () => void;
  /** Distinct tokens this message shares with at least one other orphan
   * message in the feed. Empty Set when the message is solo or already
   * attached to a case. */
  coMentionMatches: Set<string>;
}) {
  const t = ev.triage;
  const c = t?.classification ?? "";
  const noiseOrBad = c === "noise" || c === "bad_actor";
  // Two reasons to suggest making a case:
  //   - triage classified it as a sighting (eyewitness, single message); OR
  //   - this message co-mentions a token (likely a person's name) with
  //     at least one other orphan message — pattern looks real, not junk.
  // Either way, we never re-suggest if the message is already a case.
  const hasCoMention = coMentionMatches.size > 0;
  const suggestCase =
    !ev.incidentId && !noiseOrBad && (c === "sighting" || hasCoMention);
  const triageLabel = t
    ? t.classification === "sighting"
      ? "Sighting"
      : t.classification === "question"
        ? "Question"
        : t.classification === "ack"
          ? "Ack"
          : t.classification === "noise"
            ? "Noise"
            : t.classification === "bad_actor"
              ? "Bad actor"
              : t.classification
    : null;
  return (
    <div
      className="group relative pl-5 pr-3 py-4 border-b border-surface-300 hover:bg-white transition"
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
        {triageLabel && (
          <span
            className={
              "ml-1 px-1.5 py-[1px] rounded font-mono text-[9px] tracking-[0.14em] " +
              (t!.classification === "sighting"
                ? "bg-brand-600/10 text-brand-700"
                : t!.classification === "noise"
                  ? "bg-surface-200 text-ink-500"
                  : t!.classification === "bad_actor"
                    ? "bg-sev-critical/10 text-sev-critical"
                    : "bg-ink-100 text-ink-700")
            }
            title={`triage classification${
              t!.confidence != null ? ` · ${(t!.confidence * 100).toFixed(0)}%` : ""
            }`}
          >
            ✨ {triageLabel}
            {t!.confidence != null && (
              <span className="ml-1 opacity-70 normal-case tracking-normal">
                {(t!.confidence * 100).toFixed(0)}%
              </span>
            )}
          </span>
        )}
        <span className="ml-auto text-ink-400 normal-case tracking-normal tabular-nums">
          {fmtTime(ev.ts)}
        </span>
      </div>
      <div
        className="mt-1.5 text-[13px] text-ink-900 leading-snug line-clamp-2 cursor-pointer"
        onClick={() => {
          if (ev.incidentId) onOpen();
        }}
      >
        {ev.body}
      </div>
      {suggestCase && (
        <div className="mt-2 flex items-center gap-2 flex-wrap">
          <button
            type="button"
            onClick={onMakeCase}
            className="px-2.5 py-1 text-[11px] font-mono uppercase tracking-[0.12em] rounded-sm bg-ink-900 text-white hover:bg-ink-800 transition"
          >
            → Make a case
          </button>
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">
            {hasCoMention
              ? `co-mention: ${[...coMentionMatches].slice(0, 3).join(", ")}`
              : "triage suggests"}
          </span>
        </div>
      )}
    </div>
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

      {ev.toolCalls.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {ev.toolCalls.map((c) => (
            <ToolChip key={c.id} name={c.name} mode={c.mode} status={c.approvalStatus ?? null} />
          ))}
        </div>
      )}

      <div className="mt-2 text-[13px] text-ink-900 leading-snug">
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

function ToolChip({
  name,
  mode,
  status,
}: {
  name: string;
  mode: string;
  status: string | null;
}) {
  const meta = toolMeta(name);
  const isSuggest = mode === "suggest";
  const pending = isSuggest && (status == null || status === "pending");
  const approved = status === "approved";
  const rejected = status === "rejected";
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 px-2 py-[3px] rounded-md border font-mono text-[10px] uppercase tracking-[0.14em]",
        meta.classes,
        isSuggest && "border-dashed",
      )}
      title={`${meta.label} — ${meta.blurb}${isSuggest ? " (awaiting approval)" : ""}`}
    >
      <span className="font-medium">{meta.label}</span>
      {isSuggest && (
        <span
          className={clsx(
            "normal-case tracking-normal text-[9px] px-1 rounded-sm",
            pending && "bg-white/70 text-ink-700",
            approved && "bg-sev-low/15 text-sev-low",
            rejected && "bg-ink-200 text-ink-500 line-through",
          )}
        >
          {approved ? "approved" : rejected ? "rejected" : "needs approval"}
        </span>
      )}
    </span>
  );
}

