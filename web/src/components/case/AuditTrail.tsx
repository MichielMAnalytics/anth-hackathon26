import type { AuditEntry } from "../../lib/types";

const KIND_LABEL: Record<AuditEntry["kind"], string> = {
  consent_recorded: "consent",
  case_closed: "closed",
  broadcast_sent: "broadcast",
  operator_message: "msg",
};

function fmt(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString([], {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function AuditTrail({ entries }: { entries: AuditEntry[] }) {
  if (!entries || entries.length === 0) {
    return (
      <div>
        <div className="text-meta uppercase tracking-wider text-ink-500 mb-2">
          Audit trail
        </div>
        <div className="text-meta text-ink-500 italic">
          No actions recorded yet.
        </div>
      </div>
    );
  }
  // last 5, newest first
  const recent = [...entries]
    .sort((a, b) => new Date(b.ts).getTime() - new Date(a.ts).getTime())
    .slice(0, 5);
  return (
    <div>
      <div className="text-meta uppercase tracking-wider text-ink-500 mb-2">
        Audit trail
      </div>
      <ol className="space-y-1.5">
        {recent.map((e, i) => (
          <li
            key={`${e.ts}-${i}`}
            className="font-mono text-meta text-ink-700 border-l border-surface-300 pl-2.5"
          >
            <div className="text-ink-500">
              {fmt(e.ts)} ·{" "}
              <span className="uppercase tracking-wider">
                {KIND_LABEL[e.kind] ?? e.kind}
              </span>{" "}
              · {e.actor}
            </div>
            <div className="text-ink-900 whitespace-pre-wrap break-words">
              {e.summary}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
