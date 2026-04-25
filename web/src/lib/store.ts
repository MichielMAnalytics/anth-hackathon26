import { create } from "zustand";
import type {
  Audience,
  Incident,
  Message,
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

export type Tab = "map" | "incidents" | "stream";

interface State {
  incidents: Record<string, Incident>;
  messagesByIncident: Record<string, Message[]>;
  audiences: Audience[];
  regions: Record<Region, RegionStats>;
  selectedIncidentId: string | null;
  selectedRegion: Region | null;
  activeTab: Tab;

  setIncidents: (list: Incident[]) => void;
  upsertIncident: (inc: Incident) => void;
  appendMessage: (msg: Message) => void;
  setMessages: (incidentId: string, msgs: Message[]) => void;
  setAudiences: (a: Audience[]) => void;
  setRegions: (r: RegionStats[]) => void;
  selectIncident: (id: string | null) => void;
  selectRegion: (r: Region | null) => void;
  setTab: (t: Tab) => void;
}

export const useStore = create<State>((set) => ({
  incidents: {},
  messagesByIncident: {},
  audiences: [],
  regions: {} as Record<Region, RegionStats>,
  selectedIncidentId: null,
  selectedRegion: null,
  activeTab: "map",

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
  setTab: (t) => set({ activeTab: t }),
}));
