import { useMemo, useState } from "react";
import clsx from "clsx";
import { sendCaseMessage } from "../lib/api";
import { useStore } from "../lib/store";
import type { Channel, Incident } from "../lib/types";

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
        // for missing-person → civilians first; for medical → doctors first
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

  // default audience to first relevant on first render or incident change
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

  return (
    <div className="border-t border-surface-300 bg-surface-50 px-6 py-3 space-y-2.5">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-meta uppercase tracking-wider text-ink-500">
          Send to
        </span>
        <select
          value={audienceId}
          onChange={(e) => setAudienceId(e.target.value)}
          className="bg-surface-50 border border-surface-300 rounded-md px-2 py-1 text-sm text-ink-900 focus:outline-none focus:border-brand-600"
        >
          {relevant.length === 0 && (
            <option value="">— no audience available —</option>
          )}
          {relevant.map((a) => (
            <option key={a.id} value={a.id}>
              {a.label} · {a.count.toLocaleString()} reachable
            </option>
          ))}
        </select>

        <span className="text-meta uppercase tracking-wider text-ink-500 ml-2">
          Via
        </span>
        <div className="flex rounded-md overflow-hidden border border-surface-300">
          {(["fallback", "app", "sms"] as Channel[]).map((c) => {
            const active = via === c;
            return (
              <button
                key={c}
                onClick={() => setVia(c)}
                className={clsx(
                  "px-2.5 py-1 text-xs font-medium transition border-r border-surface-300 last:border-r-0",
                  active
                    ? "bg-brand-600 text-white"
                    : "bg-surface-50 text-ink-700 hover:bg-surface-100",
                )}
              >
                {CHANNEL_LABEL[c]}
              </button>
            );
          })}
        </div>

        <span className="ml-auto text-meta text-ink-500 hidden md:inline">
          ⌘↵ to send
        </span>
      </div>

      <div className="flex items-end gap-2">
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
          className="flex-1 resize-none bg-white border border-surface-300 rounded-md px-3 py-2 text-sm text-ink-900 leading-relaxed focus:outline-none focus:border-brand-600 focus:ring-1 focus:ring-brand-600/20"
        />
        <button
          onClick={send}
          disabled={sending || !body.trim()}
          className="px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white text-sm font-semibold rounded-md disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
        >
          {sending ? "Sending…" : "Send"}
        </button>
      </div>
    </div>
  );
}
