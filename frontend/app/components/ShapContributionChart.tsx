"use client";

import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, TooltipContentProps, XAxis, YAxis } from "recharts";
import { AXIS_TICK_STYLE, CHART_COLORS, TOOLTIP_WRAPPER_CLASS } from "./chart-colors";

interface ShapBar {
  indicator_code: string;
  indicator_name: string;
  feature_value: number | null;
  shap_value: number;
}

const POSITIVE = CHART_COLORS.sequential; // blue
const NEGATIVE = "#e34948"; // red, matches the Low-confidence badge tone elsewhere

function CustomTooltip({ active, payload }: TooltipContentProps) {
  if (!active || !payload || payload.length === 0) return null;
  const d = payload[0].payload as ShapBar;
  return (
    <div className={TOOLTIP_WRAPPER_CLASS}>
      <div className="font-medium text-ink">{d.indicator_name}</div>
      <div className={`mt-1 tabular-nums ${d.shap_value >= 0 ? "text-[#2a78d6]" : "text-[#e34948]"}`}>
        {d.shap_value >= 0 ? "+" : ""}
        {d.shap_value.toFixed(3)}
      </div>
      {d.feature_value !== null && <div className="text-ink-muted">value: {d.feature_value.toLocaleString()}</div>}
    </div>
  );
}

// Diverging SHAP bars — positive (pushes the prediction up) vs negative
// (pushes it down), sorted by magnitude. Unlike ContributionBarChart these
// do NOT sum to a 0-100 score; they sum to (predicted_value - base_value)
// in the target variable's own units (see PredictiveShap.target_variable).
export default function ShapContributionChart({ contributions }: { contributions: ShapBar[] }) {
  if (!contributions || contributions.length === 0) {
    return <div className="flex h-32 items-center justify-center text-sm text-ink-muted">No SHAP contributions available.</div>;
  }

  const sorted = [...contributions].sort((a, b) => Math.abs(b.shap_value) - Math.abs(a.shap_value)).reverse();
  const height = Math.max(160, sorted.length * 32 + 24);

  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={sorted} layout="vertical" margin={{ top: 4, right: 24, bottom: 4, left: 8 }} barCategoryGap={8}>
          <CartesianGrid horizontal={false} stroke={CHART_COLORS.grid} />
          <XAxis type="number" tick={AXIS_TICK_STYLE} axisLine={{ stroke: CHART_COLORS.axis }} tickLine={false} tickFormatter={(v: number) => v.toFixed(2)} />
          <YAxis type="category" dataKey="indicator_name" width={140} tick={AXIS_TICK_STYLE} axisLine={{ stroke: CHART_COLORS.axis }} tickLine={false} />
          <ReferenceLine x={0} stroke={CHART_COLORS.axis} />
          <Tooltip content={(props) => <CustomTooltip {...props} />} cursor={{ fill: "rgba(0,0,0,0.03)" }} />
          <Bar dataKey="shap_value" radius={2} maxBarSize={18}>
            {sorted.map((d, i) => (
              <Cell key={i} fill={d.shap_value >= 0 ? POSITIVE : NEGATIVE} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
