interface Props {
  data: number[];
  width?: number;
  height?: number;
  stroke?: string;
  fill?: string;
}

export function Sparkline({
  data,
  width = 160,
  height = 36,
  stroke = "rgb(82 82 90)",
  fill = "rgb(82 82 90 / 0.06)",
}: Props) {
  if (data.length === 0) {
    return (
      <div
        style={{ width, height }}
        className="border-b border-dashed border-surface-300"
      />
    );
  }
  const max = Math.max(1, ...data);
  const w = width / Math.max(1, data.length - 1);
  const path = data
    .map((v, i) => {
      const x = i * w;
      const y = height - (v / max) * (height - 2) - 1;
      return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
  const area = `${path} L ${(data.length - 1) * w} ${height} L 0 ${height} Z`;
  return (
    <svg
      width="100%"
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
    >
      <path d={area} fill={fill} />
      <path
        d={path}
        fill="none"
        stroke={stroke}
        strokeWidth="1.25"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
