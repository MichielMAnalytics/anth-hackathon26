import { useMemo, useState } from "react";
import clsx from "clsx";
import { sendCaseMessage } from "../lib/api";
import { useStore } from "../lib/store";
import type { Channel, Incident } from "../lib/types";
import { Select } from "./Select";

interface Props {
  incident: Incident;
}

const CHANNEL_LABEL: Record<Channel, string> = {
  fallback: "Bitchat → SMS",
  app: "Bitchat",
  sms: "SMS",
};

export function CaseComposer({ incident }: Props) {
  const audiences = useStore((s) => s.audiences);
  const [body, setBody] = useState("");
  const [via, setVia] = useState<Channel>("fallback");
  const [audienceId, setAudienceId] = useState<string>("");
  const [sending, setSending] = useState(false);

  const relevant = useMemo(() => {
    return audiences
      .filter((a) => a.regions.includes(incident.region))
      .sort((a, b) => {
        const score = (role: string) => {
          if (incident.category === "missing_person")
            return role === "civilian" ? 0 : 1;
          if (incident.category === "medical")
            return role === "doctor" ? 0 : role === "pharmacy" ? 1 : 2;
          if (incident.category === "resource_shortage")
            return role === "ngo" ? 0 : 1;
          return 0;
        };
        return score(a.roles[0] ?? "") - score(b.roles[0] ?? "");
      });
  }, [audiences, incident.region, incident.category]);

  if (audienceId === "" && relevant.length > 0) {
    setAudienceId(relevant[0].id);
  }

  async function send() {
    if (!body.trim()) return;
    setSending(true);
    await sendCaseMessage(incident.id, body, via, audienceId || undefined);
    setBody("");
    setSending(false);
  }

  function onKey(e: React.KeyboardEvent) {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      send();
    }
  }

  const canSend = !sending && !!body.trim();

  return (
    <div className="border-t border-surface-300 bg-white px-6 py-4 space-y-3">
      <div className="flex items-center gap-x-5 gap-y-2 flex-wrap">
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500 shrink-0">
            /// Send to
          </span>
          {relevant.length === 0 ? (
            <span className="text-[12.5px] text-ink-400">
              — no audience available —
            </span>
          ) : (
            <Select<string>
              value={audienceId}
              onChange={(v) => setAudienceId(v)}
              options={relevant.map((a) => ({
                value: a.id,
                label: `${a.label} · ${a.count.toLocaleString()} reachable`,
              }))}
              ariaLabel="Send to audience"
            />
          )}
        </div>

        <div className="flex items-center gap-2.5">
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">
            /// Via
          </span>
          <div className="flex items-center border border-surface-300 rounded-sm overflow-hidden">
            {(["fallback", "app", "sms"] as Channel[]).map((c) => {
              const active = via === c;
              return (
                <button
                  key={c}
                  onClick={() => setVia(c)}
                  className={clsx(
                    "px-3 py-1.5 text-[11.5px] font-medium transition border-r border-surface-300 last:border-r-0",
                    active
                      ? "bg-ink-900 text-white"
                      : "bg-white text-ink-600 hover:text-ink-900 hover:bg-surface-100",
                  )}
                >
                  {CHANNEL_LABEL[c]}
                </button>
              );
            })}
          </div>
        </div>

        <span className="ml-auto font-mono text-[10px] uppercase tracking-[0.14em] text-ink-400 hidden md:inline">
          ⌘↵ to send
        </span>
      </div>

      <div className="flex items-stretch gap-2">
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          onKeyDown={onKey}
          rows={2}
          placeholder={
            incident.category === "missing_person"
              ? "Reply on this case — e.g. 'If anyone has seen Diala, please message back with location.'"
              : incident.category === "medical"
                ? "Reply — e.g. 'Doctors near Sana'a, can anyone deliver insulin tonight?'"
                : "Reply on this case…"
          }
          className="flex-1 resize-y bg-white border border-surface-300 rounded-sm px-3 py-2.5 text-[13px] text-ink-900 leading-relaxed placeholder:text-ink-400 focus:outline-none focus:border-ink-700 transition md:min-h-[64px]"
        />
        <button
          onClick={send}
          disabled={!canSend}
          className={clsx(
            "px-5 self-end py-2.5 font-mono text-[11px] uppercase tracking-[0.14em] font-semibold rounded-sm transition shrink-0",
            canSend
              ? "bg-brand-600 hover:bg-brand-700 text-white"
              : "bg-surface-200 text-ink-400 cursor-not-allowed",
          )}
        >
          {sending ? "Sending…" : "Send"}
        </button>
      </div>
    </div>
  );
}
