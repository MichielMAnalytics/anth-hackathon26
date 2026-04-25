import clsx from "clsx";
import type { Message, Receipt } from "../lib/types";
import { useStore } from "../lib/store";
import { Receipts } from "./case/Receipts";

// stable empty fallback — selector must not return a new array each call
const NO_RECEIPTS: Receipt[] = [];

function maskPhone(p: string): string {
  if (p.length <= 4) return p;
  if (!/^[+0-9]/.test(p)) return p; // operator handle, not a phone
  return "···" + p.slice(-4);
}

function fmtTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function MessageBubble({ msg }: { msg: Message }) {
  const ex = msg.extracted ?? undefined;
  const outbound = !!msg.outbound;
  const receipts =
    useStore((s) => s.receiptsByMessage[msg.messageId]) ?? NO_RECEIPTS;
  return (
    <div
      className={clsx(
        "flex gap-3 py-3",
        outbound && "flex-row-reverse",
      )}
    >
      <div
        className={clsx(
          "w-8 h-8 rounded-full flex items-center justify-center text-meta font-mono shrink-0",
          outbound
            ? "bg-brand-600 text-white"
            : "bg-surface-200 text-ink-700",
        )}
      >
        {outbound ? "WC" : msg.from.replace(/[^0-9]/g, "").slice(-2) || "?"}
      </div>

      <div
        className={clsx(
          "flex-1 min-w-0",
          outbound && "flex flex-col items-end",
        )}
      >
        <div
          className={clsx(
            "flex items-center gap-2 text-meta text-ink-500",
            outbound && "flex-row-reverse",
          )}
        >
          <span className="font-mono">
            {outbound ? "War Child operator" : maskPhone(msg.from)}
          </span>
          <span>·</span>
          <span>{fmtTime(msg.ts)}</span>
          {outbound && msg.via && (
            <>
              <span>·</span>
              <span className="uppercase tracking-wider">via {msg.via}</span>
            </>
          )}
        </div>
        <div
          className={clsx(
            "mt-1 px-3.5 py-2 rounded-lg max-w-[640px] text-sm leading-relaxed whitespace-pre-wrap",
            outbound
              ? "bg-brand-600 text-white rounded-tr-sm"
              : "bg-surface-100 text-ink-900 border border-surface-200 rounded-tl-sm",
          )}
        >
          {msg.body}
        </div>
        {ex && !outbound && (
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {ex.location && <Tag>📍 {ex.location}</Tag>}
            {ex.distress && <Tag tone="critical">⚠ distress</Tag>}
            {(ex.needs ?? []).map((n) => (
              <Tag key={n} tone="high">
                needs: {n}
              </Tag>
            ))}
            {ex.personRef && <Tag>↪ {ex.personRef}</Tag>}
          </div>
        )}
        {outbound && receipts.length > 0 && <Receipts receipts={receipts} />}
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
        : "bg-surface-100 text-ink-700 border-surface-300";
  return (
    <span className={`text-meta px-1.5 py-0.5 rounded border ${cls}`}>
      {children}
    </span>
  );
}
