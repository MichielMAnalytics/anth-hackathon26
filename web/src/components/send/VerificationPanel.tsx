import type { BroadcastAck } from "../../lib/types";

const fmt = new Intl.NumberFormat("en-US");

export function VerificationPanel({ ack }: { ack: BroadcastAck }) {
  return (
    <div className="rounded-lg border border-sev-low/30 bg-sev-low/5 p-4">
      <div className="flex items-start gap-3">
        <div className="text-sev-low text-lg leading-none mt-0.5">✓</div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-ink-900">
            Queued for delivery
          </div>
          <div className="text-xs text-ink-700 mt-0.5">
            Sending to <span className="font-medium">{ack.audienceLabel}</span>{" "}
            via {ack.channels.join(" + ")}.
          </div>
        </div>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 pl-7">
        <Stat label="Recipients" value={fmt.format(ack.queued)} />
        <Stat label="Batches" value={String(ack.batches)} />
        <Stat
          label="ETA"
          value={
            ack.etaSeconds < 60
              ? `~${ack.etaSeconds}s`
              : `~${Math.round(ack.etaSeconds / 60)}m`
          }
        />
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-l border-sev-low/30 pl-2">
      <div className="text-meta uppercase tracking-wider text-ink-500">
        {label}
      </div>
      <div className="font-mono text-sm text-ink-900">{value}</div>
    </div>
  );
}
