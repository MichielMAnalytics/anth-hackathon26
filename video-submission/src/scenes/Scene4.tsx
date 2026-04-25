import { AbsoluteFill, interpolate, useCurrentFrame, Easing } from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";

const { fontFamily } = loadFont("normal", { weights: ["300", "400", "700", "800"], subsets: ["latin"] });

// SafeThread design tokens
const BG       = "#f8f7f4"; // warm off-white
const INK_900  = "#0f172a"; // wordmark
const INK_600  = "#475569"; // tagline
const INK_400  = "#94a3b8"; // icons / subtitle
const BRAND    = "#e62e2e"; // single red accent

// ── SVG icon glyphs (centered at 0,0, ~24 unit bounding box) ─────────────

const BluetoothIcon: React.FC<{ c: string }> = ({ c }) => (
  <g stroke={c} strokeWidth={2.2} fill="none" strokeLinecap="round" strokeLinejoin="round">
    <line x1={0} y1={-11} x2={0} y2={11} />
    {/* Upper chevron */}
    <polyline points="-6,-5 6,0 -6,5" />
    {/* Lower chevron */}
    <polyline points="-6,5 6,0" />
  </g>
);

const ChatIcon: React.FC<{ c: string }> = ({ c }) => (
  <path
    d="M -11,-7 Q -11,-13 -5,-13 L 5,-13 Q 11,-13 11,-7 L 11,2 Q 11,8 5,8 L 0,8 L -7,14 L -7,8 Q -11,8 -11,2 Z"
    fill="none" stroke={c} strokeWidth={2.2} strokeLinejoin="round" strokeLinecap="round"
  />
);

const WifiIcon: React.FC<{ c: string }> = ({ c }) => (
  <g fill="none" strokeLinecap="round">
    <circle cx={0} cy={9} r={2.5} fill={c} />
    <path d="M -6,4 Q -6,-3 0,-3 Q 6,-3 6,4" stroke={c} strokeWidth={2.2} />
    <path d="M -12,0 Q -12,-11 0,-11 Q 12,-11 12,0" stroke={c} strokeWidth={2.2} />
  </g>
);

const ORBIT_ICONS = [
  { Icon: BluetoothIcon, startAngle: 0 },
  { Icon: ChatIcon,      startAngle: (2 * Math.PI) / 3 },
  { Icon: WifiIcon,      startAngle: (4 * Math.PI) / 3 },
];

export const Scene4: React.FC = () => {
  const frame = useCurrentFrame();

  // Gentle warm light builds first
  const glowIn = interpolate(frame, [0, 25], [0, 0.7], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
    easing: Easing.out(Easing.quad),
  });
  const glowSettle = interpolate(frame, [50, 90], [0.7, 0.28], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
    easing: Easing.bezier(0.45, 0, 0.55, 1),
  });
  const glowOpacity = frame < 50 ? glowIn : glowSettle;

  // Wordmark materialises — no scale pop, just a clean quiet fade
  const wordmarkOpacity = interpolate(frame, [18, 60], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
    easing: Easing.bezier(0.45, 0, 0.55, 1),
  });
  const wordmarkY = interpolate(frame, [18, 60], [8, 0], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  // Red accent dot pulses once then settles
  const dotScale = interpolate(frame, [55, 68], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
    easing: Easing.bezier(0.34, 1.56, 0.64, 1),
  });

  // Subtitle
  const subtitleOpacity = interpolate(frame, [68, 100], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  // Tagline
  const taglineOpacity = interpolate(frame, [95, 130], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
    easing: Easing.bezier(0.45, 0, 0.55, 1),
  });
  const taglineY = interpolate(frame, [95, 130], [12, 0], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  // Icons: appear at frame 80, orbit very slowly — ~62° over 180 frames
  const iconsOpacity = interpolate(frame, [80, 115], [0, 0.65], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });
  const orbitDelta = interpolate(frame, [80, 180], [0, (Math.PI * 2) / 5.8], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
    easing: Easing.inOut(Easing.quad),
  });

  const ORBIT_R = 165;

  return (
    <AbsoluteFill style={{ background: BG, fontFamily }}>
      {/* Warm central glow — the "gentle light" */}
      <AbsoluteFill
        style={{
          background: "radial-gradient(ellipse 55% 50% at 50% 46%, #fff5e8 0%, transparent 100%)",
          opacity: glowOpacity,
        }}
      />

      {/* Orbiting icons */}
      <svg
        width={1920}
        height={1080}
        viewBox="0 0 1920 1080"
        style={{ position: "absolute", inset: 0 }}
      >
        <g opacity={iconsOpacity}>
          {ORBIT_ICONS.map(({ Icon, startAngle }, i) => {
            const angle = startAngle + orbitDelta;
            const cx = 960 + Math.cos(angle) * ORBIT_R;
            const cy = 460 + Math.sin(angle) * ORBIT_R;
            return (
              <g key={i} transform={`translate(${cx}, ${cy})`}>
                <circle r={26} fill={BG} opacity={0.85} />
                <Icon c={INK_400} />
              </g>
            );
          })}
        </g>
      </svg>

      {/* Content column — centred */}
      <div
        style={{
          position: "absolute",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          textAlign: "center",
          width: 900,
          marginTop: -30,
        }}
      >
        {/* Wordmark + red dot */}
        <div
          style={{
            opacity: wordmarkOpacity,
            transform: `translateY(${wordmarkY}px)`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 18,
            marginBottom: 20,
          }}
        >
          <span
            style={{
              fontSize: 96,
              fontWeight: 800,
              color: INK_900,
              letterSpacing: -2,
              lineHeight: 1,
            }}
          >
            SafeThread
          </span>

          {/* Single brand-red accent dot */}
          <span
            style={{
              display: "inline-block",
              width: 14,
              height: 14,
              borderRadius: "50%",
              background: BRAND,
              flexShrink: 0,
              transform: `scale(${dotScale})`,
              marginBottom: -4,
              boxShadow: `0 0 12px ${BRAND}55`,
            }}
          />
        </div>

        {/* Subtitle — spaced meta label */}
        <div
          style={{
            opacity: subtitleOpacity,
            fontSize: 15,
            fontWeight: 400,
            color: INK_400,
            letterSpacing: 5,
            textTransform: "uppercase" as const,
            marginBottom: 52,
          }}
        >
          Community Emergency Network
        </div>

        {/* Tagline */}
        <div
          style={{
            opacity: taglineOpacity,
            transform: `translateY(${taglineY}px)`,
            fontSize: 30,
            fontWeight: 300,
            color: INK_600,
            lineHeight: 1.6,
            maxWidth: 720,
            margin: "0 auto",
          }}
        >
          "When the network breaks,
          <br />
          the community becomes the network."
        </div>
      </div>
    </AbsoluteFill>
  );
};
