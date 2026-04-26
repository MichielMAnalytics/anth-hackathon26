import clsx from "clsx";
import { useStore } from "../lib/store";
import type { Message } from "../lib/types";

function maskPhone(p: string): string {
  if (p.length <= 4) return p;
  if (!/^[+0-9]/.test(p)) return p;
  return "···" + p.slice(-4);
}

function lastDigits(p: string, n: number): string {
  const d = p.replace(/[^0-9]/g, "");
  if (d.length === 0) return "?";
  return d.slice(-n);
}

function fmtTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function initials(name?: string | null): string {
  if (!name) return "OP";
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "OP";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export interface MessageBubbleProps {
  msg: Message;
  isFirstInGroup: boolean;
  isLastInGroup: boolean;
}

export function MessageBubble({
  msg,
  isFirstInGroup,
  isLastInGroup,
}: MessageBubbleProps) {
  const me = useStore((s) => s.me);
  const ex = msg.extracted ?? undefined;
  const outbound = !!msg.outbound;

  return (
    <div
      className={clsx(
        "flex w-full",
        outbound ? "justify-end" : "justify-start",
        isFirstInGroup ? "mt-4" : "mt-1",
        isLastInGroup && "mb-1",
      )}
    >
      <div
        className={clsx(
          "flex gap-2.5 max-w-[640px] min-w-0",
          outbound ? "flex-row-reverse" : "flex-row",
        )}
      >
        {/* Avatar — only on the first message of a group; placeholder space otherwise to preserve alignment */}
        <div className="w-7 shrink-0">
          {isFirstInGroup &&
            (outbound ? (
              <div
                className="w-7 h-7 rounded-sm bg-ink-900 flex items-center justify-center text-white font-mono text-[10px] font-semibold tracking-[0.04em] leading-none"
                aria-hidden
              >
                {initials(me?.name)}
              </div>
            ) : (
              <div
                className="relative w-7 h-7 rounded-full bg-surface-200 flex items-center justify-center font-mono text-[10px] font-semibold text-ink-700 leading-none"
                aria-hidden
              >
                {lastDigits(msg.from, 2)}
                <img
                  src="/bitchat.png"
                  alt=""
                  className="absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 rounded-[3px] bg-white p-px ring-1 ring-surface-300"
                />
              </div>
            ))}
        </div>

        <div className={clsx("flex flex-col min-w-0", outbound && "items-end")}>
          {/* Header line shown only on first message of a group */}
          {isFirstInGroup && (
            <div
              className={clsx(
                "flex items-center gap-1.5 mb-1 font-mono text-[10px] uppercase tracking-[0.14em]",
                outbound ? "flex-row-reverse text-brand-600" : "text-ink-500",
              )}
            >
              {outbound ? (
                <span className="font-semibold text-brand-600">
                  {me?.name ?? "Operator"}
                </span>
              ) : (
                <>
                  <span className="font-semibold text-ink-700">
                    {maskPhone(msg.from)}
                  </span>
                  <span className="text-surface-400">·</span>
                  <img
                    src="/bitchat.png"
                    alt=""
                    className="w-3 h-3 rounded-[2px]"
                  />
                  <span className="text-ink-500">Bitchat</span>
                </>
              )}
            </div>
          )}

          {/* Bubble */}
          <div
            className={clsx(
              "px-3.5 py-2.5 text-[13.5px] leading-relaxed whitespace-pre-wrap break-words rounded-2xl",
              outbound
                ? "bg-ink-900 text-white"
                : "bg-surface-200/70 text-ink-900",
              // tail: tighter top corner pointing toward sender on first of group
              isFirstInGroup && (outbound ? "rounded-tr-sm" : "rounded-tl-sm"),
            )}
          >
            {msg.body}
          </div>

          {/* Tags from extracted info */}
          {ex && !outbound && isLastInGroup && (
            <div className="mt-1.5 flex flex-wrap gap-1">
              {ex.location && <Tag>{ex.location}</Tag>}
              {ex.distress && <Tag tone="critical">distress</Tag>}
              {(ex.needs ?? []).map((n) => (
                <Tag key={n} tone="high">
                  needs · {n}
                </Tag>
              ))}
              {ex.personRef && <Tag>{ex.personRef}</Tag>}
            </div>
          )}

          {/* Time + via — bottom of group only */}
          {isLastInGroup && (
            <div
              className={clsx(
                "mt-1 font-mono text-[10px] tracking-[0.1em] text-ink-400",
                outbound ? "text-right" : "text-left",
              )}
            >
              {fmtTime(msg.ts)}
              {outbound && msg.via && (
                <>
                  <span className="text-surface-400"> · </span>
                  <span className="uppercase">via {msg.via}</span>
                </>
              )}
            </div>
          )}
        </div>
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
      ? "text-sev-critical border-sev-critical/30"
      : tone === "high"
        ? "text-sev-high border-sev-high/30"
        : "text-ink-700 border-surface-300";
  return (
    <span
      className={clsx(
        "font-mono text-[10px] uppercase tracking-[0.12em] px-1.5 py-0.5 rounded-sm border bg-white",
        cls,
      )}
    >
      {children}
    </span>
  );
}
