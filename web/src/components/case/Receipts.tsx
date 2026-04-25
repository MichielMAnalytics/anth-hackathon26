import type { Receipt } from "../../lib/types";

const STATUS_STYLE: Record<Receipt["status"], string> = {
  accepted: "bg-sev-low/10 text-sev-low border-sev-low/30",
  completed: "bg-sev-low/10 text-sev-low border-sev-low/30",
  declined: "bg-surface-100 text-ink-500 border-surface-300",
};

const STATUS_LABEL: Record<Receipt["status"], string> = {
  accepted: "accepted",
  completed: "completed",
  declined: "declined",
};

export function Receipts({ receipts }: { receipts: Receipt[] }) {
  if (!receipts || receipts.length === 0) return null;
  return (
    <div className="mt-1.5 flex flex-wrap gap-1.5 justify-end">
      {receipts.map((r) => (
        <span
          key={r.id}
          className={`text-meta px-1.5 py-0.5 rounded border ${STATUS_STYLE[r.status]}`}
          title={r.note ?? ""}
        >
          <span className="font-medium">{r.responder}</span>{" "}
          <span className="uppercase tracking-wider">
            {STATUS_LABEL[r.status]}
          </span>
          {r.etaMinutes !== undefined && r.status !== "declined" && (
            <span className="font-mono ml-1">· ETA {r.etaMinutes}m</span>
          )}
        </span>
      ))}
    </div>
  );
}
