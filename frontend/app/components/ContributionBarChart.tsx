"use client";

import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, TooltipContentProps, XAxis, YAxis } from "recharts";
import { AXIS_TICK_STYLE, CHART_COLORS, TOOLTIP_WRAPPER_CLASS } from "./chart-colors";

interface ContributionBar {
  code: string;
  name: string;
  contribution: number;
  raw_value: number | null;
  unit: string;
}

function CustomTooltip({ active, payload }: TooltipContentProps) {
  if (!active || !payload || payload.length === 0) return null;
  const d = payload[0].payload as ContributionBar;
  return (
    <div className={TOOLTIP_WRAPPER_CLASS}>
      <div className="font-medium text-ink">{d.name}</div>
      <div className="mt-1 tabular-nums text-ink-secondary">+{d.contribution.toFixed(1)} score points</div>
      {d.raw_value !== null && (
        <div className="text-ink-muted">
          raw: {d.raw_value.toLocaleString()} {d.unit}
        </div>
      )}
    </div>
  );
}

// Score-point contributions that sum exactly to opportunity_score (see
// app/ml/scoring.py compute_scores) — this bar chart IS the "explanation is
// the product" requirement, not a rough importance gesture.
export default function ContributionBarChart({ indicators }: { indicators: ContributionBar[] }) {
  if (!indicators || indicators.length === 0) {
    return <div className="flex h-32 items-center justify-center text-sm text-ink-muted">No indicators available.</div>;
  }

  const sorted = [...indicators].sort((a, b) => b.contribution - a.contribution);
  const height = Math.max(160, sorted.length * 36 + 24);

  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={sorted} layout="vertical" margin={{ top: 4, right: 32, bottom: 4, left: 8 }} barCategoryGap={10}>
          <CartesianGrid horizontal={false} stroke={CHART_COLORS.grid} />
          <XAxis
            type="number"
            tick={AXIS_TICK_STYLE}
            axisLine={{ stroke: CHART_COLORS.axis }}
            tickLine={false}
            tickFormatter={(v: number) => v.toFixed(0)}
          />
          <YAxis type="category" dataKey="name" width={150} tick={AXIS_TICK_STYLE} axisLine={{ stroke: CHART_COLORS.axis }} tickLine={false} />
          <Tooltip content={(props) => <CustomTooltip {...props} />} cursor={{ fill: "rgba(0,0,0,0.03)" }} />
          <Bar dataKey="contribution" radius={[0, 4, 4, 0]} maxBarSize={22}>
            {sorted.map((_, i) => (
              <Cell key={i} fill={CHART_COLORS.sequential} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
