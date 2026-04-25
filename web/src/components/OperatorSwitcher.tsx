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
        className="flex items-center gap-2 pl-1 pr-1 sm:pr-2 py-1 rounded-full border border-surface-300 bg-white hover:bg-surface-50"
        aria-label={`Operator ${me.name}, ${me.role}`}
      >
        <img
          alt=""
          src={`https://api.dicebear.com/9.x/avataaars/svg?seed=${me.avatarSeed}`}
          className="w-6 h-6 rounded-full bg-surface-200"
        />
        <div className="hidden sm:block text-left leading-tight">
          <div className="text-meta font-medium text-ink-900 truncate max-w-[140px]">
            {me.name}
          </div>
          <div
            className={clsx(
              "text-[10px] uppercase tracking-wider",
              isSenior ? "text-brand-700" : "text-ink-500",
            )}
          >
            {me.role}
            {!isSenior && me.regions.length > 0 && (
              <>
                {" · "}
                {me.regions.map((r) => REGION_LABEL[r] ?? r).join(", ")}
              </>
            )}
          </div>
        </div>
        <span className="hidden sm:inline text-ink-500 text-xs ml-0.5">▾</span>
      </button>

      {open && (
        <div className="absolute right-0 mt-1.5 w-72 bg-white border border-surface-300 rounded-lg shadow-modal z-40 overflow-hidden">
          <div className="px-3 py-2 border-b border-surface-200 text-meta uppercase tracking-wider text-ink-500 bg-surface-50">
            Switch operator
          </div>
          <ul>
            {operators.map((op) => {
              const active = op.id === me.id;
              return (
                <li key={op.id}>
                  <button
                    onClick={() => {
                      setCurrentOperatorId(op.id);
                      // hard-reload so all queries re-issue with the new header
                      window.location.reload();
                    }}
                    className={clsx(
                      "w-full text-left px-3 py-2.5 flex items-center gap-3 transition",
                      active
                        ? "bg-brand-50/50"
                        : "hover:bg-surface-50",
                    )}
                  >
                    <img
                      alt=""
                      src={`https://api.dicebear.com/9.x/avataaars/svg?seed=${op.avatarSeed}`}
                      className="w-8 h-8 rounded-full bg-surface-200 shrink-0"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-ink-900 truncate">
                        {op.name}
                      </div>
                      <div className="text-meta text-ink-500 mt-0.5">
                        <span
                          className={clsx(
                            "uppercase tracking-wider",
                            op.role === "senior"
                              ? "text-brand-700"
                              : "text-ink-500",
                          )}
                        >
                          {op.role}
                        </span>
                        {op.role === "senior" ? (
                          <> · all regions</>
                        ) : (
                          <>
                            {" · "}
                            {op.regions
                              .map((r) => REGION_LABEL[r] ?? r)
                              .join(", ") || "no region"}
                          </>
                        )}
                      </div>
                    </div>
                    {active && (
                      <span className="text-brand-600 text-sm leading-none">●</span>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
          <div className="px-3 py-2 border-t border-surface-200 text-meta text-ink-500 bg-surface-50">
            Junior operators are scoped to their assigned region and cannot
            broadcast to civilian masses.
          </div>
        </div>
      )}
    </div>
  );
}
