import { useEffect, useMemo, useRef } from "react";
import { useStore } from "../lib/store";
import { fetchMessages } from "../lib/api";
import { MessageBubble } from "./MessageBubble";
import { CaseComposer } from "./CaseComposer";
import { SeverityChip } from "./SeverityChip";
import type { Message } from "../lib/types";

const REGION_LABEL: Record<string, string> = {
  IRQ_BAGHDAD: "Baghdad, Iraq",
  IRQ_MOSUL: "Mosul, Iraq",
  SYR_ALEPPO: "Aleppo, Syria",
  SYR_DAMASCUS: "Damascus, Syria",
  YEM_SANAA: "Sana'a, Yemen",
  LBN_BEIRUT: "Beirut, Lebanon",
};

// Two messages from the same sender within this window collapse into a group.
const GROUP_GAP_MS = 2 * 60 * 1000;

interface GroupedMessage extends Message {
  isFirstInGroup: boolean;
  isLastInGroup: boolean;
}

function groupMessages(messages: Message[]): GroupedMessage[] {
  return messages.map((m, i) => {
    const prev = i > 0 ? messages[i - 1] : null;
    const next = i < messages.length - 1 ? messages[i + 1] : null;

    const sameSender = (a: Message | null, b: Message) =>
      !!a && a.from === b.from && !!a.outbound === !!b.outbound;

    const withinGap = (a: Message | null, b: Message) =>
      !!a &&
      Math.abs(new Date(b.ts).getTime() - new Date(a.ts).getTime()) <
        GROUP_GAP_MS;

    const groupedWithPrev =
      prev != null && sameSender(prev, m) && withinGap(prev, m);
    const groupedWithNext =
      next != null && sameSender(next, m) && withinGap(m, next);

    return {
      ...m,
      isFirstInGroup: !groupedWithPrev,
      isLastInGroup: !groupedWithNext,
    };
  });
}

export function CaseThread() {
  const selectedId = useStore((s) => s.selectedIncidentId);
  const incident = useStore((s) =>
    s.selectedIncidentId ? s.incidents[s.selectedIncidentId] : null,
  );
  const messagesMap = useStore((s) => s.messagesByIncident);
  const messages = useMemo(
    () => (selectedId ? (messagesMap[selectedId] ?? []) : []),
    [selectedId, messagesMap],
  );
  const setMessages = useStore((s) => s.setMessages);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Refetch on selected change AND whenever the incident object changes
  // (App.tsx calls upsertIncident for every WS event, replacing the
  // reference). That covers inbound replies threading onto the case via
  // `inbound_triaged`, outbound broadcasts via `incident_upserted`, and
  // edits — without a separate per-event subscription here.
  useEffect(() => {
    if (!selectedId) return;
    fetchMessages(selectedId).then((m) => setMessages(selectedId, m));
  }, [selectedId, incident, setMessages]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length, selectedId]);

  if (!incident) {
    return (
      <div className="h-full flex flex-col items-center justify-center bg-white px-6">
        <div className="text-center max-w-sm">
          <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-400">
            /// No case selected
          </div>
          <div className="font-display text-[18px] text-ink-700 tracking-tight mt-2">
            Select a case to view its conversation.
          </div>
          <div className="text-[12.5px] text-ink-500 mt-2 leading-relaxed">
            Messages from civilians signed into the SafeThread network appear
            here as they arrive.
          </div>
        </div>
      </div>
    );
  }

  const sorted = [...messages].sort(
    (a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime(),
  );
  const grouped = groupMessages(sorted);

  return (
    <div className="h-full flex flex-col bg-white">
      <div className="px-6 py-4 border-b border-surface-300 bg-white">
        <div className="flex items-center gap-3 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">
          <span>/// Case</span>
          <span className="text-surface-400">·</span>
          <SeverityChip severity={incident.severity} />
        </div>
        <div className="mt-2 flex items-baseline gap-3 flex-wrap">
          <h2 className="font-display text-[20px] font-semibold text-ink-900 tracking-tighter leading-tight">
            {incident.title}
          </h2>
          <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">
            {REGION_LABEL[incident.region] ?? incident.region}
            <span className="text-surface-400"> · </span>
            <span className="text-ink-700">{incident.messageCount}</span> msg
            {incident.replyCode && (
              <>
                <span className="text-surface-400"> · </span>
                reply code{" "}
                <span className="text-ink-900 font-semibold tracking-wider">
                  {incident.replyCode}
                </span>
              </>
            )}
          </div>
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-4 bg-surface-100">
        {grouped.length === 0 && (
          <div className="py-10 text-center text-[13px] text-ink-500">
            No messages yet.
          </div>
        )}
        {grouped.map((m) => (
          <MessageBubble
            key={m.messageId}
            msg={m}
            isFirstInGroup={m.isFirstInGroup}
            isLastInGroup={m.isLastInGroup}
          />
        ))}
      </div>

      <CaseComposer incident={incident} />
    </div>
  );
}
