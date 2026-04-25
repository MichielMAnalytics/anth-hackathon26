export function Field({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-ink-500">
        {label}
      </div>
      <div className="mt-0.5 text-sm text-ink-100">
        {value === undefined || value === null || value === "" ? (
          <span className="text-ink-500">—</span>
        ) : (
          value
        )}
      </div>
    </div>
  );
}
