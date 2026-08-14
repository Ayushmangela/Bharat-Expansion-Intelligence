"use client";

import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, TooltipContentProps } from "recharts";
import { CHART_COLORS, TOOLTIP_WRAPPER_CLASS } from "./chart-colors";

interface StatusSlice {
  status: string;
  count: number;
}

const MAX_SLICES = 7; // fold anything past this into "Other" rather than generating a 9th hue

function CustomTooltip({ active, payload }: TooltipContentProps) {
  if (!active || !payload || payload.length === 0) return null;
  const d = payload[0].payload as { status: string; count: number; pct: number };
  return (
    <div className={TOOLTIP_WRAPPER_CLASS}>
      <div className="font-medium text-ink">{d.status}</div>
      <div className="tabular-nums text-ink-secondary">
        {d.count.toLocaleString()} ({d.pct.toFixed(1)}%)
      </div>
    </div>
  );
}

export default function CompanyStatusPieChart({ breakdown }: { breakdown: StatusSlice[] }) {
  const total = breakdown.reduce((sum, s) => sum + s.count, 0);

  if (!breakdown || breakdown.length === 0 || total === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-ink-muted">
        No company status data yet.
      </div>
    );
  }

  const sorted = [...breakdown].sort((a, b) => b.count - a.count);
  const head = sorted.slice(0, MAX_SLICES);
  const rest = sorted.slice(MAX_SLICES);
  const restCount = rest.reduce((sum, s) => sum + s.count, 0);
  const slices = restCount > 0 ? [...head, { status: "Other", count: restCount }] : head;

  const data = slices.map((s) => ({ ...s, pct: (s.count / total) * 100 }));

  return (
    <div style={{ width: "100%", height: 280 }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
          <Pie
            data={data}
            dataKey="count"
            nameKey="status"
            cx="38%"
            cy="50%"
            innerRadius={56}
            outerRadius={92}
            paddingAngle={2}
            stroke="#ffffff"
            strokeWidth={2}
            isAnimationActive={false}
          >
            {data.map((_, i) => (
              <Cell key={i} fill={CHART_COLORS.categorical[i % CHART_COLORS.categorical.length]} />
            ))}
          </Pie>
          <Tooltip content={(props) => <CustomTooltip {...props} />} />
          <Legend
            layout="vertical"
            verticalAlign="middle"
            align="right"
            iconType="circle"
            iconSize={8}
            formatter={(value: string) => <span className="text-xs text-ink-secondary">{value}</span>}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
