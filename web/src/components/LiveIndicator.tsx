import { useEffect, useState } from "react";
import clsx from "clsx";
import type { StreamStatus } from "../lib/api";

interface Props {
  status: StreamStatus;
  lastEventTs: number | null; // epoch ms of most recent event, if any
}

function formatAge(ms: number): string {
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h`;
  return `${Math.floor(h / 24)}d`;
}

export function LiveIndicator({ status, lastEventTs }: Props) {
  // Re-render every 10s so the elapsed label stays current.
  const [, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((n) => n + 1), 10_000);
    return () => clearInterval(id);
  }, []);

  const ageMs = lastEventTs ? Date.now() - lastEventTs : null;

  let label: string;
  let dot: string;
  let text: string;
  let title: string;

  if (status === "closed") {
    label = "Offline";
    dot = "bg-sev-critical";
    text = "text-sev-critical";
    title = "Disconnected from live stream";
  } else if (status === "connecting") {
    label = "Connecting";
    dot = "bg-sev-high animate-pulse-dot";
    text = "text-sev-high";
    title = "Reconnecting to live stream…";
  } else if (ageMs == null) {
    label = "Live";
    dot = "bg-sev-low animate-pulse-dot";
    text = "text-ink-500";
    title = "Connected. Waiting for first event.";
  } else if (ageMs < 30_000) {
    label = "Live";
    dot = "bg-sev-low animate-pulse-dot";
    text = "text-ink-500";
    title = `Last event ${formatAge(ageMs)} ago`;
  } else {
    const age = formatAge(ageMs);
    label = `Idle · ${age}`;
    dot = "bg-sev-low/70";
    text = "text-ink-400";
    title = `Connected. No events for ${age}.`;
  }

  return (
    <span
      title={title}
      className="inline-flex items-center gap-1.5 select-none"
    >
      <span className={clsx("w-1.5 h-1.5 rounded-full shrink-0", dot)} />
      <span
        className={clsx(
          "font-mono text-[10px] uppercase tracking-[0.14em] tabular-nums",
          text,
        )}
      >
        {label}
      </span>
    </span>
  );
}
