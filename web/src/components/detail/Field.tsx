export function Field({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  const empty = value === undefined || value === null || value === "";
  return (
    <div>
      <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">
        {label}
      </div>
      <div className="mt-1 text-[13px] text-ink-900 leading-relaxed">
        {empty ? <span className="text-ink-400">—</span> : value}
      </div>
    </div>
  );
}
