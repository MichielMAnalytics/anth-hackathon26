import { useEffect, useRef, useState } from "react";
import clsx from "clsx";

export interface SelectOption<T extends string> {
  value: T;
  label: string;
}

interface Props<T extends string> {
  value: T;
  onChange: (v: T) => void;
  options: SelectOption<T>[];
  ariaLabel?: string;
  className?: string;
  /** Maximum width of the dropdown panel; defaults to fit-content of trigger */
  menuWidthClass?: string;
}

export function Select<T extends string>({
  value,
  onChange,
  options,
  ariaLabel,
  className,
  menuWidthClass,
}: Props<T>) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  const selected = options.find((o) => o.value === value);

  return (
    <div ref={ref} className={clsx("relative inline-block", className)}>
      <button
        type="button"
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className={clsx(
          "flex items-center gap-2 bg-white border rounded-sm px-2.5 py-1 text-[12.5px] text-ink-900 font-medium transition cursor-pointer min-h-[28px]",
          open
            ? "border-ink-700"
            : "border-surface-300 hover:border-ink-400",
        )}
      >
        <span className="truncate">
          {selected?.label ?? <span className="text-ink-400">Select…</span>}
        </span>
        <svg
          className={clsx(
            "w-3 h-3 text-ink-500 shrink-0 transition-transform",
            open && "rotate-180",
          )}
          viewBox="0 0 12 12"
          fill="none"
        >
          <path
            d="M3 4.5L6 7.5L9 4.5"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      {open && (
        <ul
          role="listbox"
          className={clsx(
            "absolute left-0 top-full mt-1 z-[1000] bg-white border border-surface-300 rounded-sm shadow-modal overflow-hidden py-1 max-h-[280px] overflow-y-auto",
            menuWidthClass ?? "min-w-full w-max max-w-[360px]",
          )}
        >
          {options.map((o) => {
            const active = o.value === value;
            return (
              <li key={o.value}>
                <button
                  type="button"
                  role="option"
                  aria-selected={active}
                  onClick={() => {
                    onChange(o.value);
                    setOpen(false);
                  }}
                  className={clsx(
                    "w-full text-left px-3 py-1.5 text-[12.5px] flex items-center justify-between gap-3 transition",
                    active
                      ? "bg-surface-100 text-ink-900 font-medium"
                      : "text-ink-700 hover:bg-surface-100/60 hover:text-ink-900",
                  )}
                >
                  <span className="truncate">{o.label}</span>
                  {active && (
                    <span
                      className="w-1.5 h-1.5 rounded-full bg-brand-600 shrink-0"
                      aria-hidden
                    />
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
