import clsx from "clsx";
import type { Channel } from "../../lib/types";

interface Props {
  value: Channel;
  onChange: (c: Channel) => void;
}

const OPTIONS: {
  id: Channel;
  label: string;
  hint: string;
  recommended?: boolean;
}[] = [
  {
    id: "fallback",
    label: "App, then SMS",
    hint: "Try the in-app channel first; fall back to SMS for offline phones.",
    recommended: true,
  },
  {
    id: "app",
    label: "App only",
    hint: "Only reach phones currently online with the app installed.",
  },
  {
    id: "sms",
    label: "SMS only",
    hint: "Send via SMS to every phone in the audience. Slower, more reliable.",
  },
];

export function ChannelSelector({ value, onChange }: Props) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
      {OPTIONS.map((o) => {
        const active = o.id === value;
        return (
          <button
            type="button"
            key={o.id}
            onClick={() => onChange(o.id)}
            className={clsx(
              "text-left rounded-lg border px-3 py-2.5 transition",
              active
                ? "border-brand-600 bg-brand-50 ring-1 ring-brand-600/20"
                : "border-surface-300 bg-white hover:bg-surface-100",
            )}
          >
            <div className="flex items-center gap-2">
              <div
                className={clsx(
                  "w-3.5 h-3.5 rounded-full border-2",
                  active ? "border-brand-600 bg-brand-600" : "border-surface-400",
                )}
              />
              <div className="text-sm font-medium text-ink-900">
                {o.label}
              </div>
              {o.recommended && (
                <span className="text-meta uppercase tracking-wider text-brand-700 border border-brand-200 bg-white px-1.5 py-px rounded ml-auto">
                  recommended
                </span>
              )}
            </div>
            <div className="text-xs text-ink-600 mt-1 leading-snug">
              {o.hint}
            </div>
          </button>
        );
      })}
    </div>
  );
}
