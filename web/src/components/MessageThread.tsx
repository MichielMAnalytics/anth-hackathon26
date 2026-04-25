import { useEffect, useMemo, useRef } from "react";
import { useStore } from "../lib/store";
import { fetchMessages } from "../lib/api";
import { MessageBubble } from "./MessageBubble";

export function MessageThread() {
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
      <div className="h-full flex items-center justify-center text-sm text-paper-600">
        Select an incident to view its message thread.
      </div>
    );
  }

  const sorted = [...messages].sort(
    (a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime(),
  );

  return (
    <div className="h-full flex flex-col bg-paper-50">
      <div className="px-6 py-4 border-b border-paper-200">
        <div className="text-meta uppercase tracking-wider text-paper-500">
          Thread
        </div>
        <div className="font-display text-xl text-paper-900 mt-0.5">
          {incident.title}
        </div>
      </div>
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-6">
        {sorted.length === 0 && (
          <div className="py-10 text-sm text-paper-600">No messages yet.</div>
        )}
        {sorted.map((m) => (
          <MessageBubble key={m.messageId} msg={m} />
        ))}
      </div>
      <div className="px-6 py-3 border-t border-paper-200 text-meta text-paper-500 italic">
        Read-only feed. The routing agent decides which messages land here.
      </div>
    </div>
  );
}
