import { AbsoluteFill, interpolate, useCurrentFrame, Easing, Sequence } from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";

const { fontFamily } = loadFont("normal", { weights: ["400", "500", "600", "700"], subsets: ["latin"] });

// Design tokens
const SURFACE     = "#f8fafc";
const SURFACE_200 = "#eef2f6";
const SURFACE_300 = "#e2e8f0";
const SURFACE_400 = "#cbd5e1";
const INK_900     = "#0f172a";
const INK_500     = "#64748b";
const INK_400     = "#94a3b8";
const BRAND       = "#e62e2e";
const SEV_HIGH    = "#b07636";
const SEV_LOW     = "#3f7d4f";
const SEV_MED     = "#a17e2e";

const PROCESSING_START = 180;
const HUMAN_START      = 420;

// ── Shared city-map grid ───────────────────────────────────────────────────
const CityMap: React.FC<{ opacity?: number }> = ({ opacity = 1 }) => (
  <g opacity={opacity}>
    {[180, 360, 540, 720, 900].map((y) => (
      <line key={`mh${y}`} x1={0} y1={y} x2={1920} y2={y} stroke={SURFACE_400} strokeWidth={2} />
    ))}
    {[320, 640, 960, 1280, 1600].map((x) => (
      <line key={`mv${x}`} x1={x} y1={0} x2={x} y2={1080} stroke={SURFACE_400} strokeWidth={2} />
    ))}
    {Array.from({ length: 26 }).map((_, i) => (
      <line key={`h${i}`} x1={0} y1={40 * i} x2={1920} y2={40 * i} stroke={SURFACE_200} strokeWidth={1} />
    ))}
    {Array.from({ length: 48 }).map((_, i) => (
      <line key={`v${i}`} x1={40 * i} y1={0} x2={40 * i} y2={1080} stroke={SURFACE_200} strokeWidth={1} />
    ))}
  </g>
);

// Small phone node for relay / endpoint
const PhoneNode: React.FC<{ cx: number; cy: number; lit?: boolean; scale?: number }> = ({
  cx, cy, lit, scale = 1,
}) => {
  const w = 36 * scale, h = 64 * scale, r = 7 * scale;
  return (
    <g>
      <rect x={cx - w / 2} y={cy - h / 2} width={w} height={h} rx={r}
        fill="#fff" stroke={lit ? SEV_HIGH : SURFACE_400} strokeWidth={lit ? 2.5 : 2} />
      <rect x={cx - w / 4} y={cy - h / 2 + 6 * scale} width={w / 2} height={4 * scale} rx={2}
        fill={SURFACE_300} />
      {lit && <circle cx={cx} cy={cy + 8 * scale} r={5 * scale} fill={SEV_HIGH} opacity={0.9} />}
    </g>
  );
};

// ── 5A.1 — Phone UI ───────────────────────────────────────────────────────
const MSGS = [
  { text: "My daughter is missing. 7 years old, yellow shirt, last seen near the market.", time: "17:42", color: BRAND,    startFrame: 20 },
  { text: "Need insulin. Block 14.",                                                       time: "17:43", color: SEV_HIGH, startFrame: 54 },
  { text: "Don't take Route 9 — flooded.",                                                 time: "17:44", color: SEV_LOW,  startFrame: 80 },
];

const Scene5PhoneUI: React.FC = () => {
  const frame   = useCurrentFrame();
  const fadeIn  = interpolate(frame, [0, 18],  [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
  const fadeOut = interpolate(frame, [88, 110], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  return (
    <AbsoluteFill
      style={{
        background: SURFACE,
        opacity: fadeIn * fadeOut,
        fontFamily,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {/* Phone shell */}
      <div
        style={{
          width: 500,
          height: 840,
          borderRadius: 44,
          background: "#fff",
          border: `3px solid ${SURFACE_300}`,
          boxShadow: "0 32px 100px rgba(15,23,42,0.10)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: "20px 24px 14px",
            borderBottom: `1px solid ${SURFACE_200}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "#fff",
          }}
        >
          <span style={{ fontFamily: "monospace", fontSize: 15, color: INK_400 }}>17:42</span>
          <span style={{ fontSize: 20, fontWeight: 700, color: INK_900, letterSpacing: -0.5 }}>SafeThread</span>
          <span style={{ fontSize: 12, color: INK_400, letterSpacing: 1 }}>●●●</span>
        </div>

        {/* Zone bar */}
        <div style={{ padding: "8px 24px", background: SURFACE, borderBottom: `1px solid ${SURFACE_200}` }}>
          <span style={{ fontSize: 12, color: INK_400, letterSpacing: 3, textTransform: "uppercase" as const }}>
            Community · Zone 4 · 127 nodes
          </span>
        </div>

        {/* Messages */}
        <div style={{ flex: 1, padding: "20px", display: "flex", flexDirection: "column", gap: 14 }}>
          {MSGS.map((m, i) => {
            const op     = interpolate(frame, [m.startFrame, m.startFrame + 14], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            const slideY = interpolate(frame, [m.startFrame, m.startFrame + 14], [10, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
            return (
              <div key={i} style={{ opacity: op, transform: `translateY(${slideY}px)` }}>
                <div
                  style={{
                    background: SURFACE,
                    border: `1px solid ${SURFACE_300}`,
                    borderLeft: `4px solid ${m.color}`,
                    borderRadius: "4px 10px 10px 4px",
                    padding: "12px 16px",
                  }}
                >
                  <div style={{ fontSize: 18, color: INK_900, lineHeight: 1.55, marginBottom: 6 }}>
                    {m.text}
                  </div>
                  <div style={{ fontFamily: "monospace", fontSize: 13, color: INK_400 }}>
                    {m.time} · mesh
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ── 5A.2 — Transport visualization ────────────────────────────────────────
const SRC = { x: 260, y: 540 };
const BT_NODES  = [{ x: 540, y: 340 }, { x: 760, y: 600 }, { x: 1020, y: 280 }, { x: 1300, y: 480 }];
const BT_END    = { x: 1680, y: 290 };
const SMS_MID   = { x: 960, y: 540 };
const SMS_END   = { x: 1680, y: 540 };
const WIFI_MID  = { x: 960, y: 780 };
const WIFI_END  = { x: 1680, y: 790 };

const clipPolyline = (pts: { x: number; y: number }[], progress: number): string => {
  if (progress >= 1) return pts.map((p) => `${p.x},${p.y}`).join(" ");
  const total   = pts.length - 1;
  const reached = Math.max(0.001, progress * total);
  const seg     = Math.min(total - 1, Math.floor(reached));
  const t       = reached - Math.floor(reached);
  const result  = pts.slice(0, seg + 1).map((p) => `${p.x},${p.y}`);
  result.push(`${pts[seg].x + (pts[seg + 1].x - pts[seg].x) * t},${pts[seg].y + (pts[seg + 1].y - pts[seg].y) * t}`);
  return result.join(" ");
};

const TravelDot: React.FC<{
  color: string;
  waypoints: { x: number; y: number }[];
  startF: number;
  duration: number;
  frame: number;
}> = ({ color, waypoints, startF, duration, frame }) => {
  const p = interpolate(frame, [startF, startF + duration], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
    easing: Easing.bezier(0.45, 0, 0.55, 1),
  });
  if (p <= 0) return null;
  const n   = waypoints.length - 1;
  const seg = Math.min(n - 1, Math.floor(p * n));
  const t   = p * n - seg;
  const cx  = waypoints[seg].x + (waypoints[seg + 1].x - waypoints[seg].x) * t;
  const cy  = waypoints[seg].y + (waypoints[seg + 1].y - waypoints[seg].y) * t;
  const op  = interpolate(p, [0.9, 1], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <circle cx={cx} cy={cy} r={10} fill={color} opacity={op}
      style={{ filter: `drop-shadow(0 0 6px ${color}88)` }} />
  );
};

const Scene5Transport: React.FC = () => {
  const frame   = useCurrentFrame();
  const fadeIn  = interpolate(frame, [0, 20],   [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const fadeOut = interpolate(frame, [95, 110],  [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  const lineProg = interpolate(frame, [5, 55], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const iconOp = interpolate(frame, [12, 40], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  const btPts   = [SRC, ...BT_NODES, BT_END];
  const smsPts  = [SRC, SMS_MID, SMS_END];
  const wifiPts = [SRC, WIFI_MID, WIFI_END];

  return (
    <AbsoluteFill style={{ background: SURFACE, opacity: fadeIn * fadeOut, fontFamily }}>
      <svg width={1920} height={1080} viewBox="0 0 1920 1080" style={{ position: "absolute", inset: 0 }}>
        <CityMap opacity={0.75} />

        {/* Path trails */}
        {lineProg > 0 && (
          <>
            <polyline points={clipPolyline(btPts,   lineProg)} fill="none" stroke={BRAND}    strokeWidth={2} strokeDasharray="8 6" opacity={0.5} />
            <polyline points={clipPolyline(smsPts,  lineProg)} fill="none" stroke={SEV_HIGH} strokeWidth={2} strokeDasharray="8 6" opacity={0.5} />
            <polyline points={clipPolyline(wifiPts, lineProg)} fill="none" stroke={SEV_LOW}  strokeWidth={2} strokeDasharray="8 6" opacity={0.5} />
          </>
        )}

        {/* Source phone */}
        <PhoneNode cx={SRC.x} cy={SRC.y} scale={1.4} />

        {/* BT relay nodes */}
        {BT_NODES.map((n, i) => <PhoneNode key={i} cx={n.x} cy={n.y} />)}

        {/* Endpoint icons */}
        {/* BT endpoint — cluster of phones */}
        <g opacity={iconOp}>
          <PhoneNode cx={BT_END.x - 26} cy={BT_END.y + 8} />
          <PhoneNode cx={BT_END.x}      cy={BT_END.y - 14} />
          <PhoneNode cx={BT_END.x + 26} cy={BT_END.y + 12} />
          <text x={BT_END.x} y={BT_END.y + 72} textAnchor="middle" fill={INK_400}
            fontSize={14} fontFamily={fontFamily} letterSpacing={3}>BT MESH</text>
        </g>

        {/* SMS tower */}
        <g opacity={iconOp}>
          <line x1={SMS_END.x} y1={SMS_END.y + 46} x2={SMS_END.x} y2={SMS_END.y - 46} stroke={INK_400} strokeWidth={3} />
          <line x1={SMS_END.x - 26} y1={SMS_END.y - 4} x2={SMS_END.x + 26} y2={SMS_END.y - 4} stroke={INK_400} strokeWidth={2.5} />
          <path d={`M ${SMS_END.x - 42} ${SMS_END.y - 52} Q ${SMS_END.x} ${SMS_END.y - 92} ${SMS_END.x + 42} ${SMS_END.y - 52}`}
            fill="none" stroke={INK_400} strokeWidth={2} />
          <path d={`M ${SMS_END.x - 26} ${SMS_END.y - 38} Q ${SMS_END.x} ${SMS_END.y - 62} ${SMS_END.x + 26} ${SMS_END.y - 38}`}
            fill="none" stroke={INK_400} strokeWidth={2} opacity={0.6} />
          <text x={SMS_END.x} y={SMS_END.y + 72} textAnchor="middle" fill={INK_400}
            fontSize={14} fontFamily={fontFamily} letterSpacing={3}>SMS</text>
        </g>

        {/* WiFi arc */}
        <g opacity={iconOp}>
          <circle cx={WIFI_END.x} cy={WIFI_END.y + 32} r={4} fill={INK_400} />
          <path d={`M ${WIFI_END.x - 18} ${WIFI_END.y + 16} Q ${WIFI_END.x} ${WIFI_END.y - 2} ${WIFI_END.x + 18} ${WIFI_END.y + 16}`}
            fill="none" stroke={INK_400} strokeWidth={2.5} />
          <path d={`M ${WIFI_END.x - 34} ${WIFI_END.y} Q ${WIFI_END.x} ${WIFI_END.y - 34} ${WIFI_END.x + 34} ${WIFI_END.y}`}
            fill="none" stroke={INK_400} strokeWidth={2.5} />
          <path d={`M ${WIFI_END.x - 50} ${WIFI_END.y - 18} Q ${WIFI_END.x} ${WIFI_END.y - 64} ${WIFI_END.x + 50} ${WIFI_END.y - 18}`}
            fill="none" stroke={INK_400} strokeWidth={2} opacity={0.6} />
          <text x={WIFI_END.x} y={WIFI_END.y + 76} textAnchor="middle" fill={INK_400}
            fontSize={14} fontFamily={fontFamily} letterSpacing={3}>INTERNET</text>
        </g>

        {/* Travelling dots */}
        <TravelDot color={BRAND}    waypoints={btPts}   startF={25} duration={80} frame={frame} />
        <TravelDot color={SEV_HIGH} waypoints={smsPts}  startF={30} duration={70} frame={frame} />
        <TravelDot color={SEV_LOW}  waypoints={wifiPts} startF={34} duration={72} frame={frame} />
      </svg>

      <div style={{ position: "absolute", bottom: 68, width: "100%", textAlign: "center" }}>
        <span style={{ fontSize: 22, color: INK_400, letterSpacing: 0.4 }}>
          Bluetooth mesh · SMS · Internet — three transports, one network
        </span>
      </div>
    </AbsoluteFill>
  );
};

// ── 5A orchestrator ────────────────────────────────────────────────────────
const Scene5Sending: React.FC = () => (
  <AbsoluteFill>
    <Sequence from={0}  durationInFrames={110} premountFor={0}><Scene5PhoneUI /></Sequence>
    <Sequence from={70} durationInFrames={110} premountFor={30}><Scene5Transport /></Sequence>
  </AbsoluteFill>
);

// ── 5B.1 — Convergence ────────────────────────────────────────────────────
const HEX_CX = 960;
const HEX_CY = 480;
const HEX_R  = 80;

const hexPts = (cx: number, cy: number, r: number) =>
  Array.from({ length: 6 }, (_, i) => {
    const a = (Math.PI / 3) * i - Math.PI / 6;
    return `${cx + r * Math.cos(a)},${cy + r * Math.sin(a)}`;
  }).join(" ");

const Scene5Convergence: React.FC = () => {
  const frame   = useCurrentFrame();
  const fadeIn  = interpolate(frame, [0, 18],  [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const fadeOut = interpolate(frame, [80, 110], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  const NUM_DOTS = 32;
  const COLORS   = [BRAND, SEV_HIGH, SEV_LOW, SEV_MED, SEV_HIGH];
  const dots = Array.from({ length: NUM_DOTS }, (_, i) => {
    const angle  = (i / NUM_DOTS) * Math.PI * 2 + (i % 3) * 0.18;
    const startR = 480 + (i % 5) * 70;
    const speed  = 0.0065 + (i % 4) * 0.0014;
    const radius = Math.max(HEX_R + 14, startR - frame * speed * 58);
    return {
      cx: HEX_CX + Math.cos(angle + frame * 0.011) * radius,
      cy: HEX_CY + Math.sin(angle + frame * 0.011) * radius,
      r: 6 + (i % 3) * 2,
      color: COLORS[i % 5],
      opacity: Math.min(0.78, ((startR - radius) / (startR - HEX_R - 14)) * 0.7 + 0.08),
    };
  });

  const hubOp = interpolate(frame, [18, 52], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ background: SURFACE, opacity: fadeIn * fadeOut, fontFamily }}>
      <svg width={1920} height={1080} viewBox="0 0 1920 1080" style={{ position: "absolute", inset: 0 }}>
        <CityMap />
        {dots.map((d, i) => (
          <circle key={i} cx={d.cx} cy={d.cy} r={d.r} fill={d.color} opacity={d.opacity} />
        ))}
        <g opacity={hubOp}>
          <polygon points={hexPts(HEX_CX, HEX_CY, HEX_R)}      fill="#fff"   stroke={SURFACE_300} strokeWidth={2.5} />
          <polygon points={hexPts(HEX_CX, HEX_CY, HEX_R - 10)} fill="none"   stroke={SURFACE_200} strokeWidth={1} />
        </g>
      </svg>
    </AbsoluteFill>
  );
};

// ── 5B.2 — Sorting ────────────────────────────────────────────────────────
const STREAMS_5B = [
  { label: "Verified",     color: SEV_LOW, y: 340 },
  { label: "Needs review", color: SEV_MED, y: 480 },
  { label: "Blocked",      color: BRAND,   y: 620 },
];

const Scene5Sorting: React.FC = () => {
  const frame   = useCurrentFrame();
  const fadeIn  = interpolate(frame, [0, 18],  [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const fadeOut = interpolate(frame, [80, 110], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  const streamProg = interpolate(frame, [14, 72], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const labelOp = interpolate(frame, [48, 75], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const aiOp    = interpolate(frame, [10, 36], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  const STREAM_END_X = HEX_CX + 920;

  return (
    <AbsoluteFill style={{ background: SURFACE, opacity: fadeIn * fadeOut, fontFamily }}>
      <svg width={1920} height={1080} viewBox="0 0 1920 1080" style={{ position: "absolute", inset: 0 }}>
        {/* Hex hub */}
        <polygon points={hexPts(HEX_CX, HEX_CY, HEX_R)}      fill="#fff"  stroke={SURFACE_300} strokeWidth={2.5} />
        <polygon points={hexPts(HEX_CX, HEX_CY, HEX_R - 10)} fill="none"  stroke={SURFACE_200} strokeWidth={1} />

        {/* Streams */}
        {STREAMS_5B.map((s, i) => {
          const x2 = HEX_CX + HEX_R + (STREAM_END_X - HEX_CX - HEX_R) * streamProg;
          const y2 = HEX_CY + (s.y - HEX_CY) * streamProg;
          return (
            <g key={i}>
              <line x1={HEX_CX + HEX_R} y1={HEX_CY} x2={x2} y2={y2}
                stroke={s.color} strokeWidth={2.5} opacity={0.6} strokeDasharray="8 6" />
              {streamProg > 0.5 && (
                <circle cx={x2} cy={y2} r={7} fill={s.color} opacity={0.8} />
              )}
            </g>
          );
        })}

        {/* Animated stream dots */}
        {streamProg > 0.7 && STREAMS_5B.flatMap((s, si) =>
          [0, 0.36, 0.68].map((phase, pi) => {
            const t   = ((frame * 0.026 + phase + si * 0.12) % 1);
            const x   = HEX_CX + HEX_R + (STREAM_END_X - HEX_CX - HEX_R) * t;
            const y   = HEX_CY + (s.y - HEX_CY) * t;
            return <circle key={`${si}_${pi}`} cx={x} cy={y} r={5} fill={s.color} opacity={0.65} />;
          })
        )}
      </svg>

      {/* AI label inside hex */}
      <div
        style={{
          position: "absolute",
          left: HEX_CX - 14,
          top: HEX_CY - 12,
          opacity: aiOp,
          fontSize: 18,
          fontWeight: 600,
          color: INK_500,
          letterSpacing: 1,
        }}
      >
        AI
      </div>

      {/* Stream labels */}
      <div
        style={{
          position: "absolute",
          right: 80,
          top: "50%",
          transform: "translateY(-50%)",
          display: "flex",
          flexDirection: "column",
          gap: 32,
        }}
      >
        {STREAMS_5B.map((s, i) => (
          <div
            key={i}
            style={{
              opacity: labelOp,
              display: "flex",
              alignItems: "center",
              gap: 12,
              fontSize: 26,
              fontWeight: 500,
              color: s.color,
            }}
          >
            <span style={{ display: "inline-block", width: 12, height: 12, borderRadius: "50%", background: s.color, flexShrink: 0 }} />
            {s.label}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

// ── 5B.3 — Heatmap pulse ─────────────────────────────────────────────────
const Scene5Heatmap: React.FC = () => {
  const frame   = useCurrentFrame();
  const fadeIn  = interpolate(frame, [0, 18], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const fadeOut = interpolate(frame, [54, 75], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  const p1 = Math.sin(frame * 0.13)       * 0.5 + 0.5;
  const p2 = Math.sin(frame * 0.10 + 1.2) * 0.5 + 0.5;
  const p3 = Math.sin(frame * 0.08 + 2.4) * 0.5 + 0.5;
  const p4 = Math.sin(frame * 0.11 + 0.7) * 0.5 + 0.5;

  const HEAT = [
    { cx: 400,  cy: 310,  rx: 190, ry: 125, p: p1, c: SEV_HIGH, base: 0.18, amp: 0.09 },
    { cx: 1120, cy: 270,  rx: 220, ry: 140, p: p2, c: SEV_MED,  base: 0.15, amp: 0.08 },
    { cx: 640,  cy: 800,  rx: 200, ry: 130, p: p3, c: BRAND,    base: 0.13, amp: 0.07 },
    { cx: 1440, cy: 700,  rx: 160, ry: 110, p: p4, c: SEV_HIGH, base: 0.14, amp: 0.06 },
    { cx: 970,  cy: 910,  rx: 240, ry: 120, p: p1, c: SEV_MED,  base: 0.12, amp: 0.06 },
  ];

  return (
    <AbsoluteFill style={{ background: SURFACE, opacity: fadeIn * fadeOut, fontFamily }}>
      <svg width={1920} height={1080} viewBox="0 0 1920 1080" style={{ position: "absolute", inset: 0 }}>
        <defs>
          {HEAT.map((h, i) => (
            <radialGradient key={i} id={`hm5b${i}`} cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor={h.c} stopOpacity={h.base + h.p * h.amp} />
              <stop offset="100%" stopColor={h.c} stopOpacity={0} />
            </radialGradient>
          ))}
        </defs>
        <CityMap />
        {HEAT.map((h, i) => (
          <ellipse key={i} cx={h.cx} cy={h.cy} rx={h.rx} ry={h.ry} fill={`url(#hm5b${i})`} />
        ))}
      </svg>
    </AbsoluteFill>
  );
};

// ── 5B orchestrator ────────────────────────────────────────────────────────
const Scene5Processing: React.FC = () => (
  <AbsoluteFill>
    <Sequence from={0}   durationInFrames={110} premountFor={0}><Scene5Convergence /></Sequence>
    <Sequence from={90}  durationInFrames={110} premountFor={30}><Scene5Sorting /></Sequence>
    <Sequence from={165} durationInFrames={75}  premountFor={30}><Scene5Heatmap /></Sequence>
  </AbsoluteFill>
);

// ── 5C.1 — Laptop / Case worker ───────────────────────────────────────────
const Scene5Laptop: React.FC = () => {
  const frame   = useCurrentFrame();
  const fadeIn  = interpolate(frame, [0, 20],  [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const fadeOut = interpolate(frame, [86, 110], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  const screenOp  = interpolate(frame, [12, 40], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const caseOp    = interpolate(frame, [36, 60], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const btnScale  = interpolate(frame, [86, 92, 98], [1, 0.87, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ background: SURFACE, opacity: fadeIn * fadeOut, fontFamily }}>
      <svg width={1920} height={1080} viewBox="0 0 1920 1080" style={{ position: "absolute", inset: 0 }}>
        {/* Screen */}
        <g opacity={screenOp}>
          <rect x={520} y={160} width={880} height={560} rx={14}
            fill="#fff" stroke={SURFACE_300} strokeWidth={2.5} />
          <rect x={542} y={182} width={836} height={516} rx={8} fill={SURFACE} />
          <text x={960} y={228} textAnchor="middle" fill={INK_500}
            fontSize={13} fontWeight="500" fontFamily={fontFamily} letterSpacing={3}>
            FIELD COORDINATOR — NGO
          </text>
          <line x1={560} y1={242} x2={1360} y2={242} stroke={SURFACE_300} strokeWidth={1} />
        </g>

        {/* Case card + button */}
        <g opacity={caseOp}>
          <rect x={580} y={264} width={700} height={130} rx={8}
            fill="#fff" stroke={SURFACE_300} strokeWidth={1.5} />
          <rect x={580} y={264} width={5} height={130} rx={2.5} fill={SEV_MED} />
          <circle cx={616} cy={329} r={11} fill={SEV_MED} />
          <text x={642} y={322} fill={SEV_MED} fontSize={11} fontWeight="600"
            fontFamily={fontFamily} letterSpacing={2}>NEEDS REVIEW</text>
          <text x={642} y={344} fill={INK_500} fontSize={13} fontFamily={fontFamily}>
            Missing child · yellow shirt · near market
          </text>
          <text x={642} y={364} fill={INK_400} fontSize={12} fontFamily={fontFamily}>
            3 corroborating mesh nodes · 17:42
          </text>

          <g transform={`translate(960, 456) scale(${btnScale})`}>
            <rect x={-72} y={-26} width={144} height={52} rx={8} fill={BRAND} />
            <text x={0} y={8} textAnchor="middle" fill="#fff"
              fontSize={16} fontWeight="600" fontFamily={fontFamily}>Confirm ✓</text>
          </g>
        </g>

        {/* Laptop base */}
        <g opacity={screenOp}>
          <rect x={460} y={720} width={1000} height={34} rx={6}
            fill="#fff" stroke={SURFACE_300} strokeWidth={2} />
          <rect x={740} y={754} width={440} height={16} rx={5} fill={SURFACE_200} />
        </g>
      </svg>
    </AbsoluteFill>
  );
};

// ── 5C.2 — Broadcast back out ─────────────────────────────────────────────
const LIGHT_NODES = [
  { x: 310,  y: 250 }, { x: 1560, y: 290 }, { x: 470,  y: 810 },
  { x: 1420, y: 830 }, { x: 960,  y: 155 }, { x: 195,  y: 580 },
  { x: 1730, y: 650 },
];

const Scene5Broadcast: React.FC = () => {
  const frame  = useCurrentFrame();
  const fadeIn = interpolate(frame, [0, 18], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  const confirmed   = frame >= 30;
  const dotColor    = confirmed ? SEV_LOW : SEV_MED;

  const radiate     = interpolate(frame, [30, 90],  [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
  const radiateR    = interpolate(radiate, [0, 1], [24, 540]);
  const radiateOp   = interpolate(radiate, [0, 0.5, 1], [0.65, 0.3, 0]);

  const nodeProg    = interpolate(frame, [36, 92],  [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const captionOp   = interpolate(frame, [75, 95],  [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ background: SURFACE, opacity: fadeIn, fontFamily }}>
      <svg width={1920} height={1080} viewBox="0 0 1920 1080" style={{ position: "absolute", inset: 0 }}>
        <CityMap opacity={0.7} />

        {/* Radiating rings */}
        <circle cx={960} cy={540} r={radiateR}        fill="none" stroke={SEV_LOW} strokeWidth={2.5} opacity={radiateOp} />
        <circle cx={960} cy={540} r={radiateR * 0.55} fill="none" stroke={SEV_LOW} strokeWidth={1.5} opacity={radiateOp * 0.5} />

        {/* Phone nodes lighting up warm amber */}
        {LIGHT_NODES.map((n, i) => {
          const delay  = i * 0.12;
          const nodeOp = interpolate(nodeProg, [delay, delay + 0.22], [0, 0.85], {
            extrapolateLeft: "clamp", extrapolateRight: "clamp",
          });
          return <PhoneNode key={i} cx={n.x} cy={n.y} lit opacity={nodeOp} />;
        })}

        {/* Central dot */}
        <circle cx={960} cy={540} r={18} fill={dotColor}
          style={{ filter: `drop-shadow(0 0 10px ${dotColor}88)` }} />
      </svg>

      <div style={{ position: "absolute", bottom: 72, width: "100%", textAlign: "center", opacity: captionOp }}>
        <div style={{ fontSize: 28, fontWeight: 500, color: INK_900, lineHeight: 1.4 }}>
          Verified. Broadcast back out.
        </div>
        <div style={{ fontSize: 20, color: INK_400, marginTop: 6 }}>
          To everyone who needs it most.
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ── 5C orchestrator ────────────────────────────────────────────────────────
const Scene5Human: React.FC = () => (
  <AbsoluteFill>
    <Sequence from={0}  durationInFrames={110} premountFor={0}><Scene5Laptop /></Sequence>
    <Sequence from={85} durationInFrames={95}  premountFor={30}><Scene5Broadcast /></Sequence>
  </AbsoluteFill>
);

// ── Scene 5 orchestrator ───────────────────────────────────────────────────
export const Scene5: React.FC = () => (
  <AbsoluteFill>
    <Sequence from={0}                durationInFrames={PROCESSING_START}               premountFor={30}>
      <Scene5Sending />
    </Sequence>
    <Sequence from={PROCESSING_START} durationInFrames={HUMAN_START - PROCESSING_START} premountFor={30}>
      <Scene5Processing />
    </Sequence>
    <Sequence from={HUMAN_START}      durationInFrames={600 - HUMAN_START}              premountFor={30}>
      <Scene5Human />
    </Sequence>
  </AbsoluteFill>
);
