import { useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { setCurrentOperatorId } from "../lib/auth";
import { useStore } from "../lib/store";

const REGION_LABEL: Record<string, string> = {
  IRQ_BAGHDAD: "Baghdad",
  IRQ_MOSUL: "Mosul",
  SYR_ALEPPO: "Aleppo",
  SYR_DAMASCUS: "Damascus",
  YEM_SANAA: "Sana'a",
  LBN_BEIRUT: "Beirut",
};

// All operators in this deployment work for War Child. If/when SafeThread
// onboards more NGOs, this becomes a per-operator field.
const ORG = {
  name: "War Child",
  logo: "/warchild.png",
};

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function OperatorSwitcher() {
  const me = useStore((s) => s.me);
  const operators = useStore((s) => s.operators);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  if (!me) return null;
  const isSenior = me.role === "senior";

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className={clsx(
          "flex items-center gap-2.5 pl-1 pr-2 py-1 rounded-md transition",
          "hover:bg-surface-100",
          open && "bg-surface-100",
        )}
        aria-label={`Operator ${me.name}, ${me.role}, ${ORG.name}`}
        aria-expanded={open}
      >
        <span className="w-7 h-7 rounded-sm bg-ink-900 flex items-center justify-center text-white font-mono text-[10.5px] font-semibold tracking-[0.04em] leading-none">
          {initials(me.name)}
        </span>
        <span className="hidden sm:flex flex-col text-left leading-tight">
          <span className="font-display text-[13px] font-semibold text-ink-900 tracking-tight truncate max-w-[160px]">
            {me.name}
          </span>
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500 mt-0.5 truncate max-w-[180px] inline-flex items-center gap-1">
            <span className={isSenior ? "text-brand-600" : "text-ink-500"}>
              {me.role}
            </span>
            <span className="text-surface-400">·</span>
            <img
              src={ORG.logo}
              alt=""
              className="w-3 h-3 rounded-[2px] object-contain"
            />
            <span className="text-ink-500">{ORG.name}</span>
          </span>
        </span>
        <svg
          className={clsx(
            "hidden sm:block w-3 h-3 text-ink-500 transition-transform",
            open && "rotate-180",
          )}
          viewBox="0 0 12 12"
          fill="none"
        >
          <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-[320px] bg-white border border-surface-300 rounded-lg shadow-modal z-[1000] overflow-hidden">
          {/* Org banner */}
          <div className="flex items-center gap-3 px-4 py-3 border-b border-surface-300 bg-surface-100/60">
            <img
              src={ORG.logo}
              alt=""
              className="w-8 h-8 rounded-sm object-cover shrink-0"
            />
            <div className="min-w-0">
              <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">
                /// Organization
              </div>
              <div className="font-display text-[14px] font-semibold text-ink-900 tracking-tight truncate">
                {ORG.name}
              </div>
            </div>
          </div>

          <div className="px-4 pt-3 pb-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">
            /// Switch operator
          </div>
          <ul className="pb-1">
            {operators.map((op) => {
              const active = op.id === me.id;
              const senior = op.role === "senior";
              return (
                <li key={op.id}>
                  <button
                    onClick={() => {
                      setCurrentOperatorId(op.id);
                      window.location.reload();
                    }}
                    className={clsx(
                      "w-full text-left px-4 py-2.5 flex items-center gap-3 transition",
                      active ? "bg-surface-100" : "hover:bg-surface-100/60",
                    )}
                  >
                    <span
                      className={clsx(
                        "w-8 h-8 rounded-sm flex items-center justify-center font-mono text-[11px] font-semibold tracking-[0.04em] leading-none shrink-0",
                        active
                          ? "bg-ink-900 text-white"
                          : "bg-surface-200 text-ink-700",
                      )}
                    >
                      {initials(op.name)}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="font-display text-[13.5px] font-semibold text-ink-900 tracking-tight truncate">
                        {op.name}
                      </div>
                      <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500 mt-0.5 truncate">
                        <span className={senior ? "text-brand-600" : "text-ink-500"}>
                          {op.role}
                        </span>
                        {senior ? (
                          <>
                            <span className="text-surface-400"> · </span>all regions
                          </>
                        ) : (
                          <>
                            <span className="text-surface-400"> · </span>
                            {op.regions
                              .map((r) => REGION_LABEL[r] ?? r)
                              .join(", ") || "no region"}
                          </>
                        )}
                      </div>
                    </div>
                    {active && (
                      <span
                        className="w-1.5 h-1.5 rounded-full bg-brand-600 shrink-0"
                        aria-label="active"
                      />
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
          <div className="px-4 py-2.5 border-t border-surface-300 text-[11.5px] text-ink-500 leading-snug">
            Junior operators are scoped to their assigned region and cannot
            broadcast to civilian masses.
          </div>
        </div>
      )}
    </div>
  );
}
