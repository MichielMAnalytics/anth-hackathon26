import { AbsoluteFill, Series } from "remotion";
import { Scene1 } from "./scenes/Scene1";
import { Scene2 } from "./scenes/Scene2";
import { Scene3 } from "./scenes/Scene3";
import { Scene4 } from "./scenes/Scene4";
import { Scene5 } from "./scenes/Scene5";
import { Scene6 } from "./scenes/Scene6";
import { Scene7 } from "./scenes/Scene7";

// Timeline: 1800 frames @ 30fps = 60 seconds
// Scene 1: 0:00–0:06   (180 frames)
// Scene 2: 0:06–0:12   (180 frames)
// Scene 3: 0:12–0:20   (240 frames)
// Scene 4: 0:20–0:26   (180 frames)
// Scene 5: 0:26–0:46   (600 frames)
// Scene 6: 0:46–0:56   (300 frames)
// Scene 7: 0:56–1:00   (120 frames)

export const AmberVideo: React.FC = () => {
  return (
    <AbsoluteFill>
      <Series>
        <Series.Sequence durationInFrames={180}>
          <Scene1 />
        </Series.Sequence>
        <Series.Sequence durationInFrames={180}>
          <Scene2 />
        </Series.Sequence>
        <Series.Sequence durationInFrames={240}>
          <Scene3 />
        </Series.Sequence>
        <Series.Sequence durationInFrames={180}>
          <Scene4 />
        </Series.Sequence>
        <Series.Sequence durationInFrames={600}>
          <Scene5 />
        </Series.Sequence>
        <Series.Sequence durationInFrames={300}>
          <Scene6 />
        </Series.Sequence>
        <Series.Sequence durationInFrames={120}>
          <Scene7 />
        </Series.Sequence>
      </Series>
    </AbsoluteFill>
  );
};
