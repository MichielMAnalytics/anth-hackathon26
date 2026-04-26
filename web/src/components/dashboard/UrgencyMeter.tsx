import clsx from "clsx";

interface Props {
  value: number; // 0-100 (or 0-1 fractional from upstream — both handled)
  size?: "sm" | "md";
}

function tone(v: number) {
  if (v >= 70) return { fill: "bg-sev-critical", text: "text-sev-critical", label: "Urgent" };
  if (v >= 40) return { fill: "bg-sev-medium", text: "text-sev-medium", label: "Watch" };
  return { fill: "bg-sev-low", text: "text-sev-low", label: "Calm" };
}

export function UrgencyMeter({ value, size = "md" }: Props) {
  const normalized = value > 0 && value < 1.5 ? value * 100 : value;
  const v = Math.round(Math.max(0, Math.min(100, normalized)));
  const t = tone(v);
  return (
    <div className="flex items-center gap-3 min-w-0">
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-[13px] text-ink-900 tabular-nums">{v}</span>
        <span className={clsx("font-mono text-[10px] uppercase tracking-[0.14em]", t.text)}>
          {t.label}
        </span>
      </div>
      <div
        className={clsx(
          "relative w-16 sm:w-20 lg:w-24 bg-surface-200 overflow-hidden rounded-full",
          size === "sm" ? "h-[3px]" : "h-1",
        )}
      >
        <div
          className={clsx("absolute inset-y-0 left-0 rounded-full transition-[width] duration-500", t.fill)}
          style={{ width: `${Math.max(v, 2)}%` }}
        />
      </div>
    </div>
  );
}
