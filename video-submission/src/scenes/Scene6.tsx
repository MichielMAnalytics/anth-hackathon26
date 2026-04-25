import { AbsoluteFill, interpolate, useCurrentFrame, Easing } from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";
import { TEAL, CORAL, YELLOW } from "./Scene2";
import { FamilyBlob } from "../components/GhostBlob";

const { fontFamily } = loadFont("normal", { weights: ["400", "600"], subsets: ["latin"] });

const SIGHTINGS = [
  {
    text: '"I saw a girl in a yellow shirt near the school."',
    x: 460,
    y: 320,
    startFrame: 15,
    dotX: 500,
    dotY: 380,
  },
  {
    text: '"Yellow shirt, heading north."',
    x: 1020,
    y: 200,
    startFrame: 50,
    dotX: 1060,
    dotY: 260,
  },
  {
    text: '"She\'s here — she\'s safe."',
    x: 1300,
    y: 450,
    startFrame: 90,
    dotX: 1340,
    dotY: 510,
  },
];

const CONVERGENCE_X = 960;
const CONVERGENCE_Y = 600;

export const Scene6: React.FC = () => {
  const frame = useCurrentFrame();

  const fadeIn = interpolate(frame, [0, 20], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  // Blobs run toward convergence point (frames 120–220)
  const blobProgress = interpolate(frame, [120, 220], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  const tealX = interpolate(blobProgress, [0, 1], [260, CONVERGENCE_X - 90]);
  const tealY = interpolate(blobProgress, [0, 1], [550, CONVERGENCE_Y]);
  const coralX = interpolate(blobProgress, [0, 1], [320, CONVERGENCE_X + 90]);
  const coralY = interpolate(blobProgress, [0, 1], [720, CONVERGENCE_Y]);
  const yellowX = interpolate(blobProgress, [0, 1], [1680, CONVERGENCE_X]);
  const yellowY = interpolate(blobProgress, [0, 1], [550, CONVERGENCE_Y - 50]);

  // Soft glow on reunion
  const glowProgress = interpolate(frame, [210, 280], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const glowR = interpolate(glowProgress, [0, 1], [60, 320]);
  const glowOpacity = interpolate(glowProgress, [0, 0.5, 1], [0, 0.45, 0.25]);

  // Final text
  const finalTextOpacity = interpolate(frame, [240, 265], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Dot convergence lines
  const lineProgress = interpolate(frame, [90, 145], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  return (
    <AbsoluteFill style={{ background: "#0f172a", opacity: fadeIn, fontFamily }}>
      <svg width={1920} height={1080} viewBox="0 0 1920 1080" style={{ position: "absolute", inset: 0 }}>
        {/* Map grid */}
        {Array.from({ length: 14 }).map((_, i) => (
          <line key={`h${i}`} x1={0} y1={80 + i * 72} x2={1920} y2={80 + i * 72} stroke="#243447" strokeWidth={1} />
        ))}
        {Array.from({ length: 20 }).map((_, i) => (
          <line key={`v${i}`} x1={96 + i * 96} y1={0} x2={96 + i * 96} y2={1080} stroke="#243447" strokeWidth={1} />
        ))}

        {/* Map roads */}
        <line x1={0} y1={540} x2={1920} y2={540} stroke="#2D3F55" strokeWidth={3} />
        <line x1={960} y1={0} x2={960} y2={1080} stroke="#2D3F55" strokeWidth={3} />
        <line x1={0} y1={300} x2={1920} y2={700} stroke="#2D3F55" strokeWidth={2} />

        {/* Convergence dot lines */}
        {SIGHTINGS.map((s, i) => {
          const endX = CONVERGENCE_X;
          const endY = CONVERGENCE_Y;
          const lx = s.dotX + (endX - s.dotX) * lineProgress;
          const ly = s.dotY + (endY - s.dotY) * lineProgress;
          return (
            <g key={i}>
              <line x1={s.dotX} y1={s.dotY} x2={lx} y2={ly} stroke={YELLOW} strokeWidth={1.5} opacity={0.4} strokeDasharray="5 7" />
              <circle cx={lx} cy={ly} r={7} fill={YELLOW} opacity={lineProgress > 0.1 ? 0.8 : 0} style={{ filter: `drop-shadow(0 0 6px ${YELLOW})` }} />
            </g>
          );
        })}

        {/* Reunion glow */}
        <circle cx={CONVERGENCE_X} cy={CONVERGENCE_Y} r={glowR} fill="#FCD34D" opacity={glowOpacity * 0.6} />
        <circle cx={CONVERGENCE_X} cy={CONVERGENCE_Y} r={glowR * 0.5} fill="#FCD34D" opacity={glowOpacity} />

        {/* Teal parent — leans right toward child */}
        <FamilyBlob x={tealX} y={tealY} scale={1.0} color={TEAL} lean={10} bobAmp={0} />

        {/* Coral parent — leans left toward child */}
        <FamilyBlob x={coralX} y={coralY} scale={1.0} color={CORAL} lean={-10} bobAmp={0} />

        {/* Yellow child */}
        <FamilyBlob x={yellowX} y={yellowY} scale={0.66} color={YELLOW} bobAmp={0} />
      </svg>

      {/* Sighting message bubbles */}
      {SIGHTINGS.map((s, i) => {
        const bubbleOpacity = interpolate(frame, [s.startFrame, s.startFrame + 18], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        const bubbleFadeOut = interpolate(frame, [100, 125], [1, 0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: s.x,
              top: s.y,
              opacity: bubbleOpacity * bubbleFadeOut,
              background: "#1E293B",
              border: `2px solid ${YELLOW}66`,
              borderRadius: 12,
              padding: "12px 18px",
              fontSize: 22,
              color: "#E5E7EB",
              maxWidth: 460,
              lineHeight: 1.4,
              boxShadow: `0 4px 20px ${YELLOW}22`,
            }}
          >
            {s.text}
          </div>
        );
      })}

      {/* Final caption */}
      <div
        style={{
          position: "absolute",
          bottom: 90,
          width: "100%",
          textAlign: "center",
          opacity: finalTextOpacity,
        }}
      >
        <div style={{ fontSize: 42, color: "#fff", fontWeight: 600, lineHeight: 1.3 }}>
          "Because in a disaster, the fastest way to find someone —<br />
          is <span style={{ color: YELLOW }}>everyone</span>."
        </div>
      </div>
    </AbsoluteFill>
  );
};
