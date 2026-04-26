import { useEffect, useRef, useState } from "react";
import clsx from "clsx";

/**
 * AgentNowPlaying — a card sized for the right-rail above "The Wire".
 *
 * Phases:
 *   idle      — subtle "Agent · idle" placeholder
 *   thinking  — pulsing brand card "Reading the bucket for Aleppo
 *               — Tamar… (2.3s)" while the multi-turn loop runs
 *   decided   — green card with the narration + model + turns + cost;
 *               auto-collapses to idle after AUTO_DISMISS_MS
 *
 * Self-contained: opens its own /ws/stream connection. Reconnects on
 * close. Never collides with the App's existing stream callback.
 */

const AUTO_DISMISS_MS = 7000;

interface ThinkingState {
  phase: "thinking";
  alertId: string | null;
  regionPrefix: string | null;
  personName: string | null;
  startedAt: number;
}

interface DecidedState {
  phase: "decided";
  alertId: string | null;
  regionPrefix: string | null;
  personName: string | null;
  narration: string;
  model: string | null;
  totalTurns: number;
  costUsd: number;
  latencyMs: number;
  isHeartbeat: boolean;
  decidedAt: number;
}

type State =
  | { phase: "idle" }
  | ThinkingState
  | DecidedState;

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

function elapsed(startMs: number): string {
  const s = Math.max(0, (Date.now() - startMs) / 1000);
  if (s < 10) return `${s.toFixed(1)}s`;
  return `${Math.floor(s)}s`;
}

function formatCost(usd: number): string {
  if (usd <= 0) return "$0.00";
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(2)}`;
}

export function AgentNowPlaying() {
  const [state, setState] = useState<State>({ phase: "idle" });
  const dismissRef = useRef<number | null>(null);
  // Re-render every 500ms while thinking so the elapsed counter ticks.
  const [, setTick] = useState(0);

  useEffect(() => {
    if (state.phase !== "thinking") return;
    const id = window.setInterval(() => setTick((n) => n + 1), 500);
    return () => window.clearInterval(id);
  }, [state.phase]);

  useEffect(() => {
    if (state.phase !== "decided") return;
    dismissRef.current = window.setTimeout(() => {
      setState({ phase: "idle" });
      dismissRef.current = null;
    }, AUTO_DISMISS_MS);
    return () => {
      if (dismissRef.current) {
        window.clearTimeout(dismissRef.current);
        dismissRef.current = null;
      }
    };
  }, [state.phase, "decidedAt" in state ? state.decidedAt : 0]);

  useEffect(() => {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const url = `${proto}://${window.location.host}/ws/stream`;
    let ws: WebSocket | null = null;
    let closed = false;

    const connect = () => {
      ws = new WebSocket(url);
      ws.onmessage = (ev) => {
        let msg: any;
        try { msg = JSON.parse(ev.data); } catch { return; }

        if (msg.type === "agent_thinking") {
          setState({
            phase: "thinking",
            alertId: msg.alertId ?? null,
            regionPrefix: msg.regionPrefix ?? null,
            personName: msg.incident?.title ?? msg.incident?.personName ?? null,
            startedAt: Date.now(),
          });
        } else if (msg.type === "decision_made") {
          const d = msg.decision ?? {};
          setState({
            phase: "decided",
            alertId: msg.alertId ?? null,
            regionPrefix: msg.regionPrefix ?? null,
            personName: msg.incident?.title ?? msg.incident?.personName ?? null,
            narration: msg.narration ?? d.narration ?? d.summary ?? "Decision made",
            model: d.model ?? null,
            totalTurns: d.totalTurns ?? 0,
            costUsd: d.costUsd ?? 0,
            latencyMs: d.latencyMs ?? 0,
            isHeartbeat: d.isHeartbeat ?? false,
            decidedAt: Date.now(),
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

  // -----------------------------------------------------------------
  // Render — card sized for the right rail
  // -----------------------------------------------------------------

  const baseClass =
    "rounded-md border px-4 py-3 transition-colors duration-300";

  if (state.phase === "idle") {
    return (
      <div className={clsx(baseClass, "bg-surface-50 border-surface-300")}>
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-sev-low/60 shrink-0" />
          <span className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-400">
            Agent · idle
          </span>
          <span className="ml-auto font-mono text-[10px] uppercase tracking-[0.14em] text-ink-300">
            standing by
          </span>
        </div>
      </div>
    );
  }

  if (state.phase === "thinking") {
    return (
      <div className={clsx(baseClass, "bg-white border-brand-600")}>
        <div className="flex items-center gap-2 mb-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-brand-600 animate-pulse-dot shrink-0" />
          <span className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-brand-600">
            Agent · thinking
          </span>
          <span className="ml-auto font-mono text-[10px] tabular-nums text-ink-400">
            {elapsed(state.startedAt)}
          </span>
        </div>
        <div className="text-[13px] text-ink-900 leading-snug">
          Reading the bucket for{" "}
          <span className="font-medium">{regionLabel(state.regionPrefix)}</span>
          {state.personName ? (
            <>
              {" — "}
              <span className="font-medium">{state.personName}</span>
            </>
          ) : null}
          …
        </div>
        <div className="mt-1 font-mono text-[10px] text-ink-400">
          Multi-turn loop in flight…
        </div>
      </div>
    );
  }

  // decided
  return (
    <div className={clsx(baseClass, "bg-white border-sev-low")}>
      <div className="flex items-center gap-2 mb-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-sev-low shrink-0" />
        <span className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-sev-low">
          Agent · decided
        </span>
        <span className="ml-auto font-mono text-[10px] tabular-nums text-ink-400">
          {regionLabel(state.regionPrefix)}
        </span>
      </div>
      <div className="text-[13px] text-ink-900 leading-snug">
        {state.narration}
      </div>
      <div className="mt-2 flex items-center gap-3 font-mono text-[10px] text-ink-400 tabular-nums">
        {state.model ? <span>{state.model}</span> : null}
        <span>{state.totalTurns} turn{state.totalTurns === 1 ? "" : "s"}</span>
        <span>{(state.latencyMs / 1000).toFixed(1)}s</span>
        <span>{formatCost(state.costUsd)}</span>
      </div>
    </div>
  );
}
