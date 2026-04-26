import { useEffect, useState } from "react";
import { sendBroadcast } from "../../lib/api";
import type {
  Audience,
  BroadcastAck,
  Channel,
  Incident,
  Region,
  SendMode,
} from "../../lib/types";
import { AudiencePicker } from "./AudiencePicker";
import { ChannelSelector } from "./ChannelSelector";
import { VerificationPanel } from "./VerificationPanel";
import { Select } from "../Select";

interface Props {
  mode: SendMode;
  incident: Incident;
  audiences: Audience[];
  onClose: () => void;
  defaults?: {
    audienceId?: string;
    body?: string;
    channel?: Channel;
    region?: Region;
  };
}

const REGION_LABEL: Record<Region, string> = {
  IRQ_BAGHDAD: "Baghdad, Iraq",
  IRQ_MOSUL: "Mosul, Iraq",
  SYR_ALEPPO: "Aleppo, Syria",
  SYR_DAMASCUS: "Damascus, Syria",
  YEM_SANAA: "Sana'a, Yemen",
  LBN_BEIRUT: "Beirut, Lebanon",
};

function defaultAudienceFor(
  mode: SendMode,
  category: Incident["category"],
  region: Region,
  audiences: Audience[],
): string {
  if (mode === "alert") {
    const civ = audiences.find(
      (a) => a.regions.includes(region) && a.roles.includes("civilian"),
    );
    return civ?.id ?? audiences[0]?.id ?? "";
  }
  if (category === "medical") {
    const inRegion = audiences.find(
      (a) => a.regions.includes(region) && a.roles.includes("doctor"),
    );
    return (
      inRegion?.id ??
      audiences.find((a) => a.roles.includes("doctor"))?.id ??
      audiences[0]?.id ??
      ""
    );
  }
  if (category === "resource_shortage") {
    return (
      audiences.find((a) => a.roles.includes("ngo"))?.id ??
      audiences[0]?.id ??
      ""
    );
  }
  return audiences[0]?.id ?? "";
}

function defaultBody(mode: SendMode, incident: Incident): string {
  if (mode === "alert") {
    const d = incident.details as Record<string, string | undefined>;
    return `AMBER ALERT — ${d.name ?? "missing person"} (${d.ageRange ?? "unknown age"}). Last seen: ${d.lastSeenLocation ?? "unknown"}. ${d.description ?? ""} If seen, reply to this number.`;
  }
  const d = incident.details as Record<string, string | undefined>;
  if (incident.category === "medical") {
    return `Medical request: ${d.medicationNeeded ?? "supplies needed"} for ${d.patientName ?? "patient"}. Location: ${d.location ?? "unknown"}. Urgency: ${d.urgency ?? "unspecified"}. Reply if you can help.`;
  }
  if (incident.category === "resource_shortage") {
    return `Resource shortage reported in ${d.location ?? "the area"}: ${d.resource ?? "supplies"} needed. Reply if you can deliver or coordinate.`;
  }
  return incident.title;
}

export function SendModal({ mode, incident, audiences, onClose, defaults }: Props) {
  const [region, setRegion] = useState<Region>(defaults?.region ?? incident.region);
  const [audienceId, setAudienceId] = useState(
    () =>
      defaults?.audienceId ??
      defaultAudienceFor(mode, incident.category, incident.region, audiences),
  );
  const [channel, setChannel] = useState<Channel>(defaults?.channel ?? "fallback");
  const [body, setBody] = useState(() => defaults?.body ?? defaultBody(mode, incident));
  const [sending, setSending] = useState(false);
  const [ack, setAck] = useState<BroadcastAck | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function submit() {
    setSending(true);
    setError(null);
    const result = (await sendBroadcast(mode, {
      incidentId: incident.id,
      audienceId,
      channels: channel,
      region,
      body,
      attachments:
        mode === "alert"
          ? {
              name: (incident.details as Record<string, unknown>).name,
              photoUrl: (incident.details as Record<string, unknown>).photoUrl,
            }
          : {},
    })) as BroadcastAck & { error?: string; reason?: string };
    setSending(false);
    if (!result.ok && result.error === "permission") {
      setError(result.reason ?? "Permission denied.");
      return;
    }
    setAck(result);
    setTimeout(onClose, 4500);
  }

  const heading = mode === "alert" ? "Send Amber Alert" : "Request Help";
  const subhead =
    mode === "alert"
      ? "Broadcast a missing-person alert. The system batches recipients automatically."
      : "Ask a targeted audience to help. We'll batch and route it for you.";

  return (
    <div
      className="fixed inset-0 z-50 bg-ink-900/40 backdrop-blur-sm flex items-start justify-center p-4 overflow-y-auto"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl bg-white border border-surface-300 rounded-xl shadow-modal mt-12"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-6 py-5 border-b border-surface-300 flex items-start justify-between">
          <div>
            <div className="text-meta uppercase tracking-wider text-ink-500">
              {mode === "alert" ? "Amber Alert" : "Resource Request"}
            </div>
            <h2 className="font-display text-2xl font-semibold text-ink-900 mt-0.5">
              {heading}
            </h2>
            <div className="text-sm text-ink-600 mt-1">{subhead}</div>
          </div>
          <button
            onClick={onClose}
            className="w-9 h-9 flex items-center justify-center text-ink-500 hover:text-ink-900 hover:bg-surface-100 rounded-full text-2xl leading-none shrink-0"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="p-6 space-y-5">
          <Section label="Message">
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              className="w-full bg-white border border-surface-300 rounded-md px-3 py-2 text-sm text-ink-900 leading-relaxed focus:outline-none focus:border-brand-600 focus:ring-1 focus:ring-brand-600/20 min-h-[110px]"
            />
          </Section>

          <Section label="Region">
            <Select<Region>
              value={region}
              onChange={(v) => setRegion(v)}
              options={Object.entries(REGION_LABEL).map(([id, label]) => ({
                value: id as Region,
                label,
              }))}
              ariaLabel="Broadcast region"
            />
          </Section>

          <Section label="Audience">
            <AudiencePicker
              audiences={audiences}
              region={region}
              selectedId={audienceId}
              onChange={setAudienceId}
            />
          </Section>

          <Section
            label="Channel"
            hint="Operators always have a SMS-only path because not everyone has Wi-Fi."
          >
            <ChannelSelector value={channel} onChange={setChannel} />
          </Section>

          {error && (
            <div className="rounded-lg border border-sev-critical/30 bg-sev-critical/5 p-3 text-sm text-sev-critical">
              <span className="font-medium">Permission denied.</span> {error}
            </div>
          )}
          {ack && <VerificationPanel ack={ack} />}
        </div>

        <div className="px-6 py-4 border-t border-surface-300 flex items-center justify-between">
          <div className="text-meta text-ink-500">
            Stub: real channel integration is wired in the next iteration.
          </div>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="px-3 py-2 text-sm text-ink-700 hover:text-ink-900 rounded-md"
            >
              Cancel
            </button>
            <button
              onClick={submit}
              disabled={sending || !!ack || !body.trim() || !audienceId}
              className="px-4 py-2 text-sm font-medium bg-brand-600 hover:bg-brand-700 text-white rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {ack ? "✓ Sent" : sending ? "Sending…" : (
                <>
                  <span className="md:hidden">Send</span>
                  <span className="hidden md:inline">{heading}</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Section({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between mb-2">
        <div className="text-meta uppercase tracking-wider text-ink-500">
          {label}
        </div>
        {hint && <div className="text-meta text-ink-500">{hint}</div>}
      </div>
      {children}
    </div>
  );
}
