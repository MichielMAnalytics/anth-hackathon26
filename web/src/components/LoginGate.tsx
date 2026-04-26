import { useEffect, useState, type ReactNode } from "react";

const STORAGE_KEY = "safethread.unlocked";

export function LoginGate({ children }: { children: ReactNode }) {
  const [unlocked, setUnlocked] = useState<boolean | null>(null);
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Decide whether the gate is needed at all. If the server has no
  // APP_PASSWORD configured, skip the gate entirely. Otherwise check the
  // local unlock flag.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch("/api/auth/required");
        const d = await r.json();
        if (cancelled) return;
        if (!d.required) {
          setUnlocked(true);
          return;
        }
        setUnlocked(localStorage.getItem(STORAGE_KEY) === "1");
      } catch {
        // If the check itself fails, fail open so the operator isn't
        // stranded by an outage of the auth endpoint.
        if (!cancelled) setUnlocked(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (unlocked === null) {
    return <div className="h-full bg-surface-100" aria-hidden />;
  }
  if (unlocked) return <>{children}</>;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setError(null);
    setSubmitting(true);
    try {
      const r = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ password }),
      });
      if (!r.ok) {
        if (r.status === 401) setError("Wrong password.");
        else setError(`Server error (${r.status}).`);
        return;
      }
      localStorage.setItem(STORAGE_KEY, "1");
      setUnlocked(true);
    } catch {
      setError("Couldn't reach the server.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="h-full flex items-center justify-center bg-surface-100 px-6">
      <form
        onSubmit={submit}
        className="w-full max-w-sm bg-white border border-surface-300 rounded-lg shadow-modal px-7 py-8 space-y-5"
      >
        <div className="flex items-center gap-2.5">
          <span
            aria-hidden
            className="w-7 h-7 rounded-md bg-ink-900 flex items-center justify-center shrink-0"
          >
            <svg viewBox="0 0 32 32" fill="none" className="w-full h-full">
              <path
                d="M 8 22 C 8 6 24 6 24 22"
                stroke="#ffffff"
                strokeWidth="2"
                strokeLinecap="round"
              />
              <circle cx="8" cy="22" r="2.5" fill="#ffffff" />
              <circle cx="16" cy="10" r="2.5" fill="#ffffff" />
              <circle cx="24" cy="22" r="2.5" fill="#ffffff" />
            </svg>
          </span>
          <span className="font-sans text-[12px] font-medium uppercase tracking-[0.22em] leading-none text-ink-900">
            SafeThread
          </span>
        </div>

        <div>
          <div className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-500">
            /// Restricted
          </div>
          <h1 className="font-display text-[28px] leading-[1.05] font-semibold text-ink-900 tracking-tightest mt-2">
            Operator console.
          </h1>
          <p className="text-[13px] text-ink-500 mt-2 leading-snug">
            Authorised personnel only. Enter the shared key to continue.
          </p>
        </div>

        <div>
          <label
            htmlFor="password"
            className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500 block mb-1.5"
          >
            Password
          </label>
          <input
            id="password"
            type="password"
            autoFocus
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={submitting}
            className="w-full border border-surface-300 rounded-md px-3 py-2.5 text-[14px] text-ink-900 bg-white focus:outline-none focus:ring-2 focus:ring-brand-600/30 focus:border-brand-600 disabled:opacity-60"
          />
          {error && (
            <p className="text-[12px] text-sev-critical mt-2 font-medium">
              {error}
            </p>
          )}
        </div>

        <button
          type="submit"
          disabled={submitting || !password}
          className="w-full bg-ink-900 text-white text-[13px] font-medium tracking-tight py-2.5 rounded-md hover:bg-ink-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {submitting ? "Checking…" : "Unlock"}
        </button>

        <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-400 pt-3 border-t border-surface-300">
          SafeThread · Restricted access
        </div>
      </form>
    </div>
  );
}
