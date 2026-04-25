import clsx from "clsx";
import type { Audience, Region } from "../../lib/types";

interface Props {
  audiences: Audience[];
  region?: Region | null;
  selectedId: string;
  onChange: (id: string) => void;
}

export function AudiencePicker({
  audiences,
  region,
  selectedId,
  onChange,
}: Props) {
  // sort: in-region first, then by count desc
  const sorted = [...audiences].sort((a, b) => {
    const ar = region ? (a.regions.includes(region) ? 0 : 1) : 0;
    const br = region ? (b.regions.includes(region) ? 0 : 1) : 0;
    if (ar !== br) return ar - br;
    return b.count - a.count;
  });

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
      {sorted.map((a) => {
        const active = a.id === selectedId;
        const inRegion = region ? a.regions.includes(region) : false;
        return (
          <button
            key={a.id}
            type="button"
            onClick={() => onChange(a.id)}
            className={clsx(
              "text-left rounded-lg border px-3 py-2.5 transition",
              active
                ? "border-brand-600 bg-brand-50 ring-1 ring-brand-600/20"
                : "border-surface-300 bg-white hover:bg-surface-100",
            )}
          >
            <div className="flex items-center gap-2">
              <div className="text-sm font-medium text-ink-900 truncate">
                {a.label}
              </div>
              {inRegion && (
                <span className="text-meta uppercase tracking-wider text-brand-700 border border-brand-200 bg-brand-50 px-1.5 py-px rounded">
                  in region
                </span>
              )}
            </div>
            <div className="text-xs text-ink-600 mt-0.5 truncate">
              {a.description}
            </div>
            <div className="mt-1.5 flex items-center gap-3 text-meta text-ink-500">
              <span className="font-mono">
                {new Intl.NumberFormat("en-US").format(a.count)} reachable
              </span>
              <span>·</span>
              <span>
                via {a.channelsAvailable.join(" + ")}
              </span>
            </div>
          </button>
        );
      })}
    </div>
  );
}
