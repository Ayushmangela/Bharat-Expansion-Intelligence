const BAND_STYLES: Record<string, string> = {
  High: "bg-[#1baf7a]/10 text-[#128a5f]",
  Moderate: "bg-[#eda100]/15 text-[#8a6000]",
  Low: "bg-[#e34948]/10 text-[#b93231]",
  Unknown: "bg-ink/5 text-ink-muted",
};

export default function ConfidenceBadge({ band, score }: { band: string; score: number }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${BAND_STYLES[band] ?? BAND_STYLES.Unknown}`}
      title={`${(score * 100).toFixed(0)}% of indicator weight present`}
    >
      {band} · {(score * 100).toFixed(0)}%
    </span>
  );
}
