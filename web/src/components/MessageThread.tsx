import { useEffect, useMemo, useRef } from "react";
import { useStore } from "../lib/store";
import { fetchMessages } from "../lib/api";
import { MessageBubble } from "./MessageBubble";

export function MessageThread() {
  const selectedId = useStore((s) => s.selectedId);
  const incident = useStore((s) =>
    s.selectedId ? s.incidents[s.selectedId] : null,
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
      <div className="h-full flex items-center justify-center text-sm text-ink-400">
        Select an incident to view its message thread.
      </div>
    );
  }

  const sorted = [...messages].sort(
    (a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime(),
  );

  return (
    <div className="h-full flex flex-col">
      <div className="px-5 py-3 border-b border-ink-800">
        <div className="text-xs uppercase tracking-wider text-ink-400">
          Thread
        </div>
        <div className="text-sm font-medium text-ink-100">{incident.title}</div>
      </div>
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-5">
        {sorted.length === 0 && (
          <div className="py-10 text-sm text-ink-400">No messages yet.</div>
        )}
        {sorted.map((m) => (
          <MessageBubble key={m.messageId} msg={m} />
        ))}
      </div>
      <div className="px-5 py-3 border-t border-ink-800 text-[11px] text-ink-500 italic">
        Read-only feed. The routing agent decides which messages land here.
      </div>
    </div>
  );
}
