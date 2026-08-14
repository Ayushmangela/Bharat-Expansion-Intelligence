import type { ReactNode } from "react";

// Meter component (dataviz skill, marks-and-anatomy.md): fill carries the
// value, the unfilled track is a lighter step of the same ramp — used here
// for the two "X of Y" coverage ratios (districts / states ingested so far)
// instead of a fabricated delta, since there is no prior snapshot to compare
// against yet.
export default function MeterTile({
  label,
  value,
  max,
  formattedValue,
  icon,
}: {
  label: string;
  value: number;
  max: number;
  formattedValue: string;
  icon: ReactNode;
}) {
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <div className="flex items-center gap-2.5">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent/10 text-accent">
          {icon}
        </span>
        <div className="text-xs font-medium text-ink-secondary">{label}</div>
      </div>
      <div className="mt-3 text-2xl font-semibold text-ink">{formattedValue}</div>
      <div className="mt-2.5 h-1.5 w-full overflow-hidden rounded-full bg-accent/15">
        <div className="h-full rounded-full bg-accent" style={{ width: `${pct}%` }} />
      </div>
      <div className="mt-1 text-xs text-ink-muted">{pct.toFixed(0)}% covered so far</div>
    </div>
  );
}
