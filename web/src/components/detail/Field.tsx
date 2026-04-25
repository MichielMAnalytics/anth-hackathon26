export function Field({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div>
      <div className="text-meta uppercase tracking-wider text-ink-500">
        {label}
      </div>
      <div className="mt-0.5 text-sm text-ink-900 leading-relaxed">
        {value === undefined || value === null || value === "" ? (
          <span className="text-ink-400">—</span>
        ) : (
          value
        )}
      </div>
    </div>
  );
}
