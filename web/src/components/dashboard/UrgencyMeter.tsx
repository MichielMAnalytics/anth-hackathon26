import clsx from "clsx";

interface Props {
  value: number; // 0-100
  size?: "sm" | "md";
}

function tone(v: number) {
  if (v >= 70) return { fill: "bg-sev-critical", label: "Urgent", text: "text-sev-critical" };
  if (v >= 40) return { fill: "bg-sev-medium", label: "Watch", text: "text-sev-medium" };
  return { fill: "bg-sev-low", label: "Calm", text: "text-sev-low" };
}

export function UrgencyMeter({ value, size = "md" }: Props) {
  const t = tone(value);
  const v = Math.max(0, Math.min(100, value));
  return (
    <div className="flex items-center gap-2.5 min-w-0">
      <div
        className={clsx(
          "relative w-32 rounded-full bg-surface-200 overflow-hidden",
          size === "sm" ? "h-1.5" : "h-2",
        )}
      >
        <div
          className={clsx("absolute inset-y-0 left-0 rounded-full", t.fill)}
          style={{ width: `${v}%` }}
        />
      </div>
      <div className="flex items-baseline gap-1.5">
        <span className="font-mono text-sm text-ink-900">{v}</span>
        <span className={clsx("text-meta uppercase tracking-wider", t.text)}>
          {t.label}
        </span>
      </div>
    </div>
  );
}
