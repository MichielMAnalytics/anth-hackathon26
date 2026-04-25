import { AbsoluteFill, interpolate, useCurrentFrame, Easing, staticFile } from "remotion";
import { Video } from "@remotion/media";
import { loadFont } from "@remotion/google-fonts/Inter";

const { fontFamily } = loadFont("normal", { weights: ["400", "600"], subsets: ["latin"] });

// Palette shared across scenes — kept here as the canonical source
export const TEAL   = "#6EC6C6";
export const CORAL  = "#F4A090";
export const YELLOW = "#FFD166";
export const PURPLE = "#B39DDB";
export const LILAC  = "#D4B8F0";
export const SAGE   = "#93C9A8";
export const MINT   = "#B8E0C8";

export const Scene2: React.FC = () => {
  const frame = useCurrentFrame();

  const fadeIn = interpolate(frame, [0, 15], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const fadeOut = interpolate(frame, [162, 180], [1, 0], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });
  const sceneOpacity = fadeIn * fadeOut;

  const captionOpacity = interpolate(frame, [30, 60], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ background: "#000" }}>
      {/* Real footage */}
      <AbsoluteFill style={{ opacity: sceneOpacity }}>
        <Video
          src={staticFile("scene2.mp4")}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </AbsoluteFill>

      {/* Bottom gradient — keeps caption readable */}
      <AbsoluteFill
        style={{
          background: "linear-gradient(to top, rgba(0,0,0,0.65) 0%, transparent 45%)",
          opacity: sceneOpacity,
        }}
      />

      {/* Caption */}
      <div
        style={{
          position: "absolute",
          bottom: 56,
          width: "100%",
          textAlign: "center",
          opacity: captionOpacity * sceneOpacity,
          fontFamily,
        }}
      >
        <span style={{ fontSize: 34, color: "#e2e8f0", fontWeight: 400, letterSpacing: 0.5 }}>
          Every community has its rhythms.
        </span>
      </div>
    </AbsoluteFill>
  );
};
