import { create } from "zustand";
import type {
  Audience,
  Category,
  Incident,
  Message,
  Operator,
  Receipt,
  Region,
  RegionStats,
  Severity,
} from "./types";

const SEV_RANK: Record<Severity, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};
export { SEV_RANK };

export type Tab = "dashboard" | "cases" | "map" | "stream";
export type IssueFilter = Category | "all";

interface State {
  incidents: Record<string, Incident>;
  messagesByIncident: Record<string, Message[]>;
  receiptsByMessage: Record<string, Receipt[]>;
  audiences: Audience[];
  regions: Record<Region, RegionStats>;
  selectedIncidentId: string | null;
  selectedRegion: Region | "all";
  issueFilter: IssueFilter;
  activeTab: Tab;
  me: Operator | null;
  operators: Operator[];

  setIncidents: (list: Incident[]) => void;
  upsertIncident: (inc: Incident) => void;
  appendMessage: (msg: Message) => void;
  setMessages: (incidentId: string, msgs: Message[]) => void;
  appendReceipt: (r: Receipt) => void;
  setAudiences: (a: Audience[]) => void;
  setRegions: (r: RegionStats[]) => void;
  selectIncident: (id: string | null) => void;
  selectRegion: (r: Region | "all") => void;
  setIssueFilter: (i: IssueFilter) => void;
  setTab: (t: Tab) => void;
  setMe: (op: Operator | null) => void;
  setOperators: (ops: Operator[]) => void;
}

export const useStore = create<State>((set) => ({
  incidents: {},
  messagesByIncident: {},
  receiptsByMessage: {},
  audiences: [],
  regions: {} as Record<Region, RegionStats>,
  selectedIncidentId: null,
  selectedRegion: "all",
  issueFilter: "all",
  activeTab: "dashboard",
  me: null,
  operators: [],

  setIncidents: (list) =>
    set({ incidents: Object.fromEntries(list.map((i) => [i.id, i])) }),
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
  appendReceipt: (r) =>
    set((s) => {
      const prev = s.receiptsByMessage[r.messageId] ?? [];
      if (prev.some((x) => x.id === r.id)) return s;
      return {
        receiptsByMessage: {
          ...s.receiptsByMessage,
          [r.messageId]: [...prev, r],
        },
      };
    }),
  setAudiences: (a) => set({ audiences: a }),
  setRegions: (r) =>
    set({
      regions: Object.fromEntries(r.map((x) => [x.region, x])) as Record<
        Region,
        RegionStats
      >,
    }),
  selectIncident: (id) => set({ selectedIncidentId: id }),
  selectRegion: (r) => set({ selectedRegion: r }),
  setIssueFilter: (i) => set({ issueFilter: i }),
  setTab: (t) => set({ activeTab: t }),
  setMe: (op) => set({ me: op }),
  setOperators: (ops) => set({ operators: ops }),
}));
