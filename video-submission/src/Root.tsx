import "./index.css";
import { Composition } from "remotion";
import { AmberVideo } from "./Composition";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="AmberAlert"
      component={AmberVideo}
      durationInFrames={1800}
      fps={30}
      width={1920}
      height={1080}
    />
  );
};
