import { useEffect, useMemo, useRef } from "react";
import { useStore } from "../lib/store";
import { fetchMessages } from "../lib/api";
import { MessageBubble } from "./MessageBubble";
import { CaseComposer } from "./CaseComposer";
import { SeverityChip } from "./SeverityChip";

const REGION_LABEL: Record<string, string> = {
  IRQ_BAGHDAD: "Baghdad, Iraq",
  IRQ_MOSUL: "Mosul, Iraq",
  SYR_ALEPPO: "Aleppo, Syria",
  SYR_DAMASCUS: "Damascus, Syria",
  YEM_SANAA: "Sana'a, Yemen",
  LBN_BEIRUT: "Beirut, Lebanon",
};

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

  useEffect(() => {
    if (!selectedId) return;
    if (!useStore.getState().messagesByIncident[selectedId]) {
      fetchMessages(selectedId).then((m) => setMessages(selectedId, m));
    }
  }, [selectedId, setMessages]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length, selectedId]);

  if (!incident) {
    return (
      <div className="h-full flex flex-col items-center justify-center bg-surface-100">
        <div className="text-ink-500 text-sm max-w-sm text-center">
          Select a case from the left to view its conversation. Messages from
          civilians signed into the Bitchat app appear here as they arrive.
        </div>
      </div>
    );
  }

  const sorted = [...messages].sort(
    (a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime(),
  );

  return (
    <div className="h-full flex flex-col bg-surface-100">
      <div className="px-6 py-3.5 border-b border-surface-300 bg-white flex items-center gap-3">
        <SeverityChip severity={incident.severity} />
        <div className="min-w-0">
          <div className="font-display text-base font-semibold text-ink-900 truncate">
            {incident.title}
          </div>
          <div className="text-meta text-ink-500 mt-0.5">
            {REGION_LABEL[incident.region] ?? incident.region} ·{" "}
            <span className="font-mono">{incident.messageCount}</span> messages
          </div>
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-4">
        {sorted.length === 0 && (
          <div className="py-10 text-sm text-ink-500">No messages yet.</div>
        )}
        {sorted.map((m) => (
          <MessageBubble key={m.messageId} msg={m} />
        ))}
      </div>

      <CaseComposer incident={incident} />
    </div>
  );
}
