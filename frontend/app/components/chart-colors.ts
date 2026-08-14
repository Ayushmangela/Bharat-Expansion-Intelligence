// Shared chart color tokens, validated for CVD-safety per the project's dataviz
// method (fixed categorical order, one sequential hue for single-series magnitude
// charts). Light-mode only, matching the rest of the app (see globals.css).

export const CHART_COLORS = {
  // Fixed-order categorical slots — assign in this order, never cycled or reassigned
  // by sort/filter, and never re-ordered per chart.
  categorical: [
    "#2a78d6", // 1 blue
    "#eb6834", // 2 orange
    "#1baf7a", // 3 aqua
    "#eda100", // 4 yellow
    "#e87ba4", // 5 magenta
    "#008300", // 6 green
    "#4a3aa7", // 7 violet
    "#e34948", // 8 red
  ],
  // Single-hue blue for single-series magnitude bars/lines.
  sequential: "#2a78d6",
  sequentialFill: "#2a78d6", // used at ~10% opacity for area washes
  grid: "#e1e0d9",
  axis: "#c3c2b7",
  muted: "#898781",
  textSecondary: "#52514e",
  textPrimary: "#0b0b0b",
} as const;

export const AXIS_TICK_STYLE = {
  fontSize: 12,
  fill: CHART_COLORS.muted,
};

export const TOOLTIP_WRAPPER_CLASS =
  "rounded-lg border border-hairline/60 bg-surface px-3 py-2 text-xs shadow-md";

export function formatMonthLabel(isoMonth: string): string {
  // isoMonth like "2025-06-01" or "2025-06"
  const d = new Date(isoMonth.length > 7 ? isoMonth : `${isoMonth}-01`);
  if (Number.isNaN(d.getTime())) return isoMonth;
  return d.toLocaleDateString("en-IN", { month: "short", year: "2-digit" });
}
