import { AbsoluteFill, interpolate, useCurrentFrame, Easing, staticFile } from "remotion";
import { Video } from "@remotion/media";
import { loadFont } from "@remotion/google-fonts/Inter";

const { fontFamily } = loadFont("normal", { weights: ["400", "600"], subsets: ["latin"] });

export const Scene3: React.FC = () => {
  const frame = useCurrentFrame();

  // Fade in from black (hard cut from Scene 2 footage)
  const fadeIn = interpolate(frame, [0, 12], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  // Vignette and dust colour grade build through the scene
  const vignetteOpacity = interpolate(frame, [10, 80], [0, 0.7], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  // Warm dust tint — bombing footage already has it, but reinforce
  const dustOpacity = interpolate(frame, [20, 100], [0, 0.18], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  // Text overlays appear once the visual has registered
  const text1Opacity = interpolate(frame, [100, 122], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const text2Opacity = interpolate(frame, [132, 155], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  // Fade to black at the end before Scene 4
  const fadeOut = interpolate(frame, [220, 240], [1, 0], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ background: "#000", opacity: fadeIn * fadeOut }}>
      {/* Rupture footage — looped so short clips fill the full 8 s */}
      <Video
        src={staticFile("scene3.mp4")}
        style={{ width: "100%", height: "100%", objectFit: "cover" }}
        loop
      />

      {/* Warm dust tint */}
      <AbsoluteFill style={{ background: "#7c3b00", opacity: dustOpacity }} />

      {/* Radial vignette */}
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(ellipse at center, transparent 25%, rgba(0,0,0,0.85) 100%)",
          opacity: vignetteOpacity,
        }}
      />

      {/* Text — bottom-center, tight editorial style */}
      <div
        style={{
          position: "absolute",
          bottom: 110,
          width: "100%",
          textAlign: "center",
          fontFamily,
        }}
      >
        <div
          style={{
            opacity: text1Opacity,
            fontSize: 48,
            fontWeight: 600,
            color: "#ffffff",
            marginBottom: 12,
            textShadow: "0 2px 12px rgba(0,0,0,0.8)",
          }}
        >
          Then everything breaks at once.
        </div>
        <div
          style={{
            opacity: text2Opacity,
            fontSize: 34,
            fontWeight: 400,
            color: "#94a3b8",
            textShadow: "0 2px 8px rgba(0,0,0,0.8)",
          }}
        >
          The networks. The roads. The families.
        </div>
      </div>
    </AbsoluteFill>
  );
};
