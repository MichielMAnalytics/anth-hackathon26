/**
 * Lightweight anomaly hint. Server already sets `RegionStats.anomaly`,
 * but this is used for the inline copy: "200 msgs in 3 min vs baseline 22".
 */
export function describeAnomaly(stats: {
  msgsPerMin: number;
  baselineMsgsPerMin: number;
}): string {
  const m3 = Math.round(stats.msgsPerMin * 3);
  const b3 = Math.max(1, Math.round(stats.baselineMsgsPerMin * 3));
  return `${m3} messages in last 3 min — usually ~${b3}.`;
}
