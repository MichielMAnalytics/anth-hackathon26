interface Props {
  data: number[];
  width?: number;
  height?: number;
}

export function Sparkline({ data, width = 160, height = 36 }: Props) {
  if (data.length === 0) {
    return (
      <div
        style={{ width, height }}
        className="border-b border-dashed border-paper-300"
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
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <path d={area} fill="rgb(58 111 111 / 0.10)" />
      <path
        d={path}
        fill="none"
        stroke="rgb(42 87 87)"
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
