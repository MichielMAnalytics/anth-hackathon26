export function Field({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div>
      <div className="text-meta uppercase tracking-wider text-paper-500">
        {label}
      </div>
      <div className="mt-0.5 text-sm text-paper-900 leading-relaxed">
        {value === undefined || value === null || value === "" ? (
          <span className="text-paper-400">—</span>
        ) : (
          value
        )}
      </div>
    </div>
  );
}
