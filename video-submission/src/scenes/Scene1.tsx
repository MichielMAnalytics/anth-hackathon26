import { AbsoluteFill, interpolate, useCurrentFrame, Easing } from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";

const { fontFamily } = loadFont("normal", { weights: ["400", "700"], subsets: ["latin"] });

// Word-by-word reveal for building tension
const LINE1 = ["1", "in", "3", "human", "trafficking", "victims", "is", "a", "child."];

// Timeline (180 frames = 6s):
// 0–20:   silence (black)
// 20–95:  line 1 word-by-word (9 words × ~8.5 frames)
// 95–135: heavy hold — the sentence just sits there
// 135–165: line 2 fades in below, line 1 dims slightly
// 165–180: both hold

const wordFade = (frame: number, i: number) => {
  const start = 20 + i * 8.5;
  return interpolate(frame, [start, start + 10], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
};

export const Scene1: React.FC = () => {
  const frame = useCurrentFrame();

  const line1Words = LINE1.map((_, i) => wordFade(frame, i));

  // Line 1 holds fully visible until 135, then dims slightly when line 2 arrives
  const line1Opacity = interpolate(frame, [135, 155], [1, 0.5], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Line 2: fades in as a whole — quiet, inevitable
  const line2Opacity = interpolate(frame, [135, 162], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.45, 0, 0.55, 1),
  });

  // Subtle upward drift on line 2 entrance (not a shift — just a gentle float-in)
  const line2Y = interpolate(frame, [135, 162], [14, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  return (
    <AbsoluteFill
      style={{
        background: "#000",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        fontFamily,
      }}
    >
      {/* Line 1 — stays centered and large throughout */}
      <div
        style={{
          opacity: line1Opacity,
          textAlign: "center",
          maxWidth: 1300,
          lineHeight: 1.15,
        }}
      >
        {LINE1.map((word, i) => (
          <span
            key={i}
            style={{
              opacity: line1Words[i],
              fontSize: 88,
              fontWeight: 700,
              color: "#fff",
              marginRight: i < LINE1.length - 1 ? 22 : 0,
              display: "inline-block",
            }}
          >
            {word}
          </span>
        ))}
      </div>

      {/* Line 2 — fades in below, smaller, quieter */}
      <div
        style={{
          opacity: line2Opacity,
          transform: `translateY(${line2Y}px)`,
          textAlign: "center",
          maxWidth: 1100,
          marginTop: 48,
        }}
      >
        <span
          style={{
            fontSize: 48,
            fontWeight: 400,
            color: "#6B7280",
            letterSpacing: 0.5,
          }}
        >
          In disasters, they disappear faster.
        </span>
      </div>
    </AbsoluteFill>
  );
};
