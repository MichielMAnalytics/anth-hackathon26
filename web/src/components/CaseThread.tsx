import { useEffect, useMemo, useRef } from "react";
import { useStore } from "../lib/store";
import { fetchMessages, postReceipt } from "../lib/api";
import { MessageBubble } from "./MessageBubble";
import { CaseComposer } from "./CaseComposer";
import { SeverityChip } from "./SeverityChip";
import type { Receipt, ReceiptStatus } from "../lib/types";

const MOCK_RESPONDERS = [
  "Dr Karim",
  "Field worker Aisha",
  "Pharmacist Yousef",
  "Nurse Layla",
  "Coordinator Omar",
  "Dr Fadi",
];

const MOCK_NOTES = [
  "On my way",
  "Stuck in traffic",
  "Need 30m",
  "Will check now",
  "Already in area",
];

function pick<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

function scheduleFakeReceipts(
  incidentId: string,
  messageId: string,
  appendReceipt: (r: Receipt) => void,
) {
  const total = 2 + Math.floor(Math.random() * 3); // 2..4
  const used = new Set<string>();
  for (let i = 0; i < total; i++) {
    const delayMs = 8000 + Math.random() * 17000; // 8s..25s
    setTimeout(() => {
      let responder = pick(MOCK_RESPONDERS);
      let attempts = 0;
      while (used.has(responder) && attempts < 6) {
        responder = pick(MOCK_RESPONDERS);
        attempts += 1;
      }
      used.add(responder);
      const roll = Math.random();
      const status: ReceiptStatus =
        roll < 0.65 ? "accepted" : roll < 0.85 ? "completed" : "declined";
      const r: Receipt = {
        id: `rcpt_${messageId}_${i}_${Math.random().toString(36).slice(2, 8)}`,
        messageId,
        responder,
        status,
        ts: new Date().toISOString(),
        ...(status === "accepted"
          ? { etaMinutes: 5 + Math.floor(Math.random() * 25) }
          : {}),
        ...(status === "declined" ? { note: pick(MOCK_NOTES) } : {}),
      };
      appendReceipt(r);
      // fire-and-forget contract call
      postReceipt(incidentId, r).catch(() => {});
    }, delayMs);
  }
}

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
  const appendReceipt = useStore((s) => s.appendReceipt);
  const scrollRef = useRef<HTMLDivElement>(null);
  const receiptsScheduledRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!selectedId) return;
    if (!useStore.getState().messagesByIncident[selectedId]) {
      fetchMessages(selectedId).then((m) => setMessages(selectedId, m));
    }
  }, [selectedId, setMessages]);

  // Schedule fake receipts for any new outbound messages (only those that
  // arrived after mount — we don't backfill receipts for old messages).
  const mountedAtRef = useRef<number>(Date.now());
  useEffect(() => {
    for (const m of messages) {
      if (!m.outbound) continue;
      if (receiptsScheduledRef.current.has(m.messageId)) continue;
      const tsMs = new Date(m.ts).getTime();
      if (tsMs < mountedAtRef.current - 5000) {
        // historical message — skip
        receiptsScheduledRef.current.add(m.messageId);
        continue;
      }
      receiptsScheduledRef.current.add(m.messageId);
      scheduleFakeReceipts(m.incidentId, m.messageId, appendReceipt);
    }
  }, [messages, appendReceipt]);

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
