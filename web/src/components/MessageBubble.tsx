import type { Message } from "../lib/types";

function maskPhone(p: string): string {
  if (p.length <= 4) return p;
  return "···" + p.slice(-4);
}

function fmtTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function MessageBubble({ msg }: { msg: Message }) {
  const ex = msg.extracted ?? undefined;
  return (
    <div className="flex gap-3 py-3 border-b border-paper-200/70 last:border-b-0">
      <div className="w-9 h-9 rounded-full bg-paper-200 flex items-center justify-center text-meta font-mono text-paper-700 shrink-0">
        {msg.from.replace(/[^0-9]/g, "").slice(-2) || "?"}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 text-meta text-paper-500">
          <span className="font-mono">{maskPhone(msg.from)}</span>
          <span>·</span>
          <span>{fmtTime(msg.ts)}</span>
        </div>
        <div className="mt-1 text-sm text-paper-900 leading-relaxed whitespace-pre-wrap">
          {msg.body}
        </div>
        {ex && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {ex.location && (
              <Tag>📍 {ex.location}</Tag>
            )}
            {ex.distress && (
              <Tag tone="critical">⚠ distress</Tag>
            )}
            {(ex.needs ?? []).map((n) => (
              <Tag key={n} tone="high">
                needs: {n}
              </Tag>
            ))}
            {ex.personRef && <Tag>↪ {ex.personRef}</Tag>}
          </div>
        )}
      </div>
    </div>
  );
}

function Tag({
  children,
  tone,
}: {
  children: React.ReactNode;
  tone?: "critical" | "high";
}) {
  const cls =
    tone === "critical"
      ? "bg-sev-critical/10 text-sev-critical border-sev-critical/30"
      : tone === "high"
        ? "bg-sev-high/10 text-sev-high border-sev-high/30"
        : "bg-paper-100 text-paper-700 border-paper-200";
  return (
    <span
      className={`text-meta px-1.5 py-0.5 rounded border ${cls}`}
    >
      {children}
    </span>
  );
}
