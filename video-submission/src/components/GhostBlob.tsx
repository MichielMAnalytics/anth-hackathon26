import { useCurrentFrame } from "remotion";

interface FamilyBlobProps {
  x: number;
  y: number;
  scale?: number;
  color: string;
  /** Slight tilt in degrees — negative leans left, positive leans right */
  lean?: number;
  bobAmp?: number;
  bobSpeed?: number;
  bobPhase?: number;
}

// Smooth pebble body — wider at base, rounder at top, ~128w × 153h units
const BODY =
  "M 0,-72 C 32,-72 60,-45 62,-8 C 64,29 52,68 12,78 C 4,81 -4,81 -12,78 C -52,68 -64,29 -62,-8 C -60,-45 -32,-72 0,-72 Z";

export const FamilyBlob: React.FC<FamilyBlobProps> = ({
  x,
  y,
  scale = 1,
  color,
  lean = 0,
  bobAmp = 10,
  bobSpeed = 0.055,
  bobPhase = 0,
}) => {
  const frame = useCurrentFrame();
  const dy = Math.sin(frame * bobSpeed + bobPhase) * bobAmp;

  const gradId = `fbg${color.replace(/[^a-zA-Z0-9]/g, "")}`;
  const shadowId = `fbs${color.replace(/[^a-zA-Z0-9]/g, "")}`;

  return (
    <g transform={`translate(${x}, ${y + dy}) scale(${scale}) rotate(${lean})`}>
      <defs>
        {/* Upper-centre highlight for soft 3-D look */}
        <radialGradient id={gradId} cx="42%" cy="22%" r="62%" gradientUnits="objectBoundingBox">
          <stop offset="0%" stopColor="#ffffff" stopOpacity={0.45} />
          <stop offset="55%" stopColor="#ffffff" stopOpacity={0.05} />
          <stop offset="100%" stopColor="#000000" stopOpacity={0.07} />
        </radialGradient>
        {/* Soft bottom shadow */}
        <filter id={shadowId} x="-40%" y="-20%" width="180%" height="160%">
          <feDropShadow dx="0" dy="14" stdDeviation="12" floodColor={color} floodOpacity={0.3} />
        </filter>
      </defs>

      {/* Body */}
      <path d={BODY} fill={color} style={{ filter: `url(#${shadowId})` }} />
      {/* Highlight overlay */}
      <path d={BODY} fill={`url(#${gradId})`} />

      {/* Eyes — small filled ovals */}
      <ellipse cx={-18} cy={-12} rx={7} ry={9} fill="#222" />
      <ellipse cx={18} cy={-12} rx={7} ry={9} fill="#222" />
      {/* Eye glints */}
      <circle cx={-15} cy={-17} r={3} fill="#fff" opacity={0.6} />
      <circle cx={21} cy={-17} r={3} fill="#fff" opacity={0.6} />

      {/* Smile */}
      <path
        d="M -16,8 Q 0,26 16,8"
        fill="none"
        stroke="#333"
        strokeWidth={3.5}
        strokeLinecap="round"
      />

      {/* Rosy cheeks */}
      <ellipse cx={-26} cy={8} rx={10} ry={7} fill="#FFB3B3" opacity={0.4} />
      <ellipse cx={26} cy={8} rx={10} ry={7} fill="#FFB3B3" opacity={0.4} />
    </g>
  );
};
