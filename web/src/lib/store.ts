import { create } from "zustand";
import type { Incident, Message, Severity } from "./types";

const SEV_RANK: Record<Severity, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

interface State {
  incidents: Record<string, Incident>;
  messagesByIncident: Record<string, Message[]>;
  selectedId: string | null;
  setIncidents: (list: Incident[]) => void;
  upsertIncident: (inc: Incident) => void;
  appendMessage: (msg: Message) => void;
  setMessages: (incidentId: string, msgs: Message[]) => void;
  select: (id: string | null) => void;
  sortedIncidents: () => Incident[];
}

export const useStore = create<State>((set, get) => ({
  incidents: {},
  messagesByIncident: {},
  selectedId: null,

  setIncidents: (list) =>
    set({
      incidents: Object.fromEntries(list.map((i) => [i.id, i])),
    }),

  upsertIncident: (inc) =>
    set((s) => ({ incidents: { ...s.incidents, [inc.id]: inc } })),

  appendMessage: (msg) =>
    set((s) => {
      const prev = s.messagesByIncident[msg.incidentId] ?? [];
      if (prev.some((m) => m.messageId === msg.messageId)) return s;
      return {
        messagesByIncident: {
          ...s.messagesByIncident,
          [msg.incidentId]: [...prev, msg],
        },
      };
    }),

  setMessages: (incidentId, msgs) =>
    set((s) => ({
      messagesByIncident: { ...s.messagesByIncident, [incidentId]: msgs },
    })),

  select: (id) => set({ selectedId: id }),

  sortedIncidents: () => {
    const list = Object.values(get().incidents);
    list.sort((a, b) => {
      const r = SEV_RANK[a.severity] - SEV_RANK[b.severity];
      if (r !== 0) return r;
      const ta = a.lastActivity ? new Date(a.lastActivity).getTime() : 0;
      const tb = b.lastActivity ? new Date(b.lastActivity).getTime() : 0;
      return tb - ta;
    });
    return list;
  },
}));
