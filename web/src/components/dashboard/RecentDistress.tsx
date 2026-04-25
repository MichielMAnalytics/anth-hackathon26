import { useStore } from "../../lib/store";
import type { RecentDistressItem } from "../../lib/types";

function fmtTime(iso: string) {
  return new Date(iso).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function maskPhone(p: string) {
  if (p.length <= 4) return p;
  if (!/^[+0-9]/.test(p)) return p;
  return "···" + p.slice(-4);
}

export function RecentDistress({ items }: { items: RecentDistressItem[] }) {
  const selectIncident = useStore((s) => s.selectIncident);
  const setTab = useStore((s) => s.setTab);

  if (items.length === 0) {
    return (
      <div className="text-meta text-ink-500">
        No distress signals in the current window.
      </div>
    );
  }

  return (
    <ul className="space-y-2">
      {items.map((m) => (
        <li key={m.messageId}>
          <button
            onClick={() => {
              selectIncident(m.incidentId);
              setTab("cases");
            }}
            className="w-full text-left rounded-md border border-surface-300 bg-white hover:bg-surface-50 px-3 py-2.5 transition"
          >
            <div className="flex items-center gap-2 text-meta text-ink-500">
              <span className="text-sev-critical">⚠</span>
              <span className="font-mono">{maskPhone(m.from)}</span>
              <span>·</span>
              <span>{m.regionLabel}</span>
              <span className="ml-auto font-mono">{fmtTime(m.ts)}</span>
            </div>
            <div className="mt-1 text-sm text-ink-900 leading-snug line-clamp-2">
              {m.body}
            </div>
          </button>
        </li>
      ))}
    </ul>
  );
}
