import { useStore } from "../../lib/store";
import { navigate } from "../../lib/router";
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

  if (items.length === 0) {
    return (
      <div className="border border-dashed border-surface-300 rounded-md px-4 py-8 text-center">
        <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-400">
          No signals
        </div>
        <div className="text-[12.5px] text-ink-500 mt-1.5">
          Quiet window. Channel is open.
        </div>
      </div>
    );
  }

  return (
    <ul className="divide-y divide-surface-300 border-y border-surface-300">
      {items.map((m, i) => (
        <li
          key={m.messageId}
          className="stagger-item"
          style={{ ["--stagger-delay" as never]: `${i * 30}ms` }}
        >
          <button
            onClick={() => {
              selectIncident(m.incidentId);
              navigate("cases");
            }}
            className="group w-full text-left py-3 hover:bg-white transition px-1"
          >
            <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">
              <span className="w-1 h-1 rounded-full bg-sev-critical" />
              <span className="text-ink-700">{maskPhone(m.from)}</span>
              <span className="text-surface-400">·</span>
              <span>{m.regionLabel}</span>
              <span className="ml-auto text-ink-400 normal-case tracking-normal">
                {fmtTime(m.ts)}
              </span>
            </div>
            <div className="mt-1.5 text-[13px] text-ink-900 leading-snug line-clamp-2 group-hover:text-ink-900">
              {m.body}
            </div>
          </button>
        </li>
      ))}
    </ul>
  );
}
