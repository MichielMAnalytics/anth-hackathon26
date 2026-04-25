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

interface Props {
  mode: SendMode;
  incident: Incident;
  audiences: Audience[];
  onClose: () => void;
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

export function SendModal({ mode, incident, audiences, onClose }: Props) {
  const [region, setRegion] = useState<Region>(incident.region);
  const [audienceId, setAudienceId] = useState(() =>
    defaultAudienceFor(mode, incident.category, incident.region, audiences),
  );
  const [channel, setChannel] = useState<Channel>("fallback");
  const [body, setBody] = useState(() => defaultBody(mode, incident));
  const [sending, setSending] = useState(false);
  const [ack, setAck] = useState<BroadcastAck | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function submit() {
    setSending(true);
    const result = await sendBroadcast(mode, {
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
    });
    setSending(false);
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
      className="fixed inset-0 z-50 bg-paper-900/30 backdrop-blur-sm flex items-start justify-center p-4 overflow-y-auto"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl bg-paper-50 border border-paper-200 rounded-xl shadow-modal mt-12"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-6 py-5 border-b border-paper-200 flex items-start justify-between">
          <div>
            <div className="text-meta uppercase tracking-wider text-paper-500">
              {mode === "alert" ? "Amber Alert" : "Resource Request"}
            </div>
            <h2 className="font-display text-2xl text-paper-900 mt-0.5">
              {heading}
            </h2>
            <div className="text-sm text-paper-600 mt-1">{subhead}</div>
          </div>
          <button
            onClick={onClose}
            className="text-paper-500 hover:text-paper-900 text-2xl leading-none"
          >
            ×
          </button>
        </div>

        <div className="p-6 space-y-5">
          <Section label="Message">
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              className="w-full bg-paper-50 border border-paper-200 rounded-md px-3 py-2 text-sm text-paper-900 leading-relaxed focus:outline-none focus:border-accent-500 focus:ring-1 focus:ring-accent-500/20 min-h-[110px]"
            />
          </Section>

          <Section label="Region">
            <select
              value={region}
              onChange={(e) => setRegion(e.target.value as Region)}
              className="bg-paper-50 border border-paper-200 rounded-md px-3 py-2 text-sm text-paper-900 focus:outline-none focus:border-accent-500"
            >
              {Object.entries(REGION_LABEL).map(([id, label]) => (
                <option key={id} value={id}>
                  {label}
                </option>
              ))}
            </select>
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

          {ack && <VerificationPanel ack={ack} />}
        </div>

        <div className="px-6 py-4 border-t border-paper-200 flex items-center justify-between">
          <div className="text-meta text-paper-500">
            Stub: real channel integration is wired in the next iteration.
          </div>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="px-3 py-2 text-sm text-paper-700 hover:text-paper-900 rounded-md"
            >
              Cancel
            </button>
            <button
              onClick={submit}
              disabled={sending || !!ack || !body.trim() || !audienceId}
              className="px-4 py-2 text-sm font-medium bg-accent-600 hover:bg-accent-700 text-paper-50 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {ack ? "✓ Sent" : sending ? "Sending…" : heading}
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
        <div className="text-meta uppercase tracking-wider text-paper-500">
          {label}
        </div>
        {hint && <div className="text-meta text-paper-500">{hint}</div>}
      </div>
      {children}
    </div>
  );
}
