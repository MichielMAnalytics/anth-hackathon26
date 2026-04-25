import type { Message } from "../lib/types";

function maskPhone(p: string): string {
  if (p.length <= 4) return p;
  return "…" + p.slice(-4);
}

function fmtTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function MessageBubble({ msg }: { msg: Message }) {
  const ex = msg.extracted ?? undefined;
  return (
    <div className="flex gap-3 py-3 border-b border-ink-800/40">
      <div className="w-8 h-8 rounded-full bg-ink-700 flex items-center justify-center text-[11px] font-mono text-ink-300 shrink-0">
        {msg.from.replace(/[^0-9]/g, "").slice(-2) || "?"}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 text-xs text-ink-400">
          <span className="font-mono">{maskPhone(msg.from)}</span>
          <span>·</span>
          <span>{fmtTime(msg.ts)}</span>
        </div>
        <div className="mt-1 text-sm text-ink-100 leading-snug whitespace-pre-wrap">
          {msg.body}
        </div>
        {ex && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {ex.location && (
              <span className="text-[11px] px-1.5 py-0.5 rounded bg-ink-800 text-ink-300 border border-ink-700">
                📍 {ex.location}
              </span>
            )}
            {ex.distress && (
              <span className="text-[11px] px-1.5 py-0.5 rounded bg-sev-critical/15 text-sev-critical border border-sev-critical/30">
                ⚠ distress
              </span>
            )}
            {(ex.needs ?? []).map((n) => (
              <span
                key={n}
                className="text-[11px] px-1.5 py-0.5 rounded bg-sev-high/15 text-sev-high border border-sev-high/30"
              >
                needs: {n}
              </span>
            ))}
            {ex.personRef && (
              <span className="text-[11px] px-1.5 py-0.5 rounded bg-ink-800 text-ink-300 border border-ink-700">
                ↪ {ex.personRef}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
