"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  TooltipContentProps,
  XAxis,
  YAxis,
} from "recharts";
import { AXIS_TICK_STYLE, CHART_COLORS, TOOLTIP_WRAPPER_CLASS } from "./chart-colors";

interface DistrictBar {
  district_name: string;
  state_name: string;
  company_count: number;
}

function CustomTooltip({ active, payload }: TooltipContentProps) {
  if (!active || !payload || payload.length === 0) return null;
  const d = payload[0].payload as DistrictBar;
  return (
    <div className={TOOLTIP_WRAPPER_CLASS}>
      <div className="font-medium text-ink">{d.district_name}</div>
      <div className="text-ink-muted">{d.state_name}</div>
      <div className="mt-1 tabular-nums text-ink-secondary">
        {d.company_count.toLocaleString()} companies
      </div>
    </div>
  );
}

export default function TopDistrictsChart({ districts }: { districts: DistrictBar[] }) {
  if (!districts || districts.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center text-sm text-ink-muted">
        No district data yet.
      </div>
    );
  }

  // Horizontal bars (longest first stays on top), one bar per district — labelled
  // with district + state so metros aren't ambiguous.
  const data = districts.map((d) => ({
    ...d,
    label: `${d.district_name}`,
  }));

  const height = Math.max(220, data.length * 36 + 40);

  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 8, right: 24, bottom: 8, left: 8 }}
          barCategoryGap={8}
        >
          <CartesianGrid horizontal={false} stroke={CHART_COLORS.grid} />
          <XAxis
            type="number"
            tick={AXIS_TICK_STYLE}
            axisLine={{ stroke: CHART_COLORS.axis }}
            tickLine={false}
            tickFormatter={(v: number) => v.toLocaleString()}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={140}
            tick={AXIS_TICK_STYLE}
            axisLine={{ stroke: CHART_COLORS.axis }}
            tickLine={false}
          />
          <Tooltip content={(props) => <CustomTooltip {...props} />} cursor={{ fill: "rgba(0,0,0,0.03)" }} />
          <Bar dataKey="company_count" radius={[0, 4, 4, 0]} maxBarSize={24}>
            {data.map((_, i) => (
              <Cell key={i} fill={CHART_COLORS.sequential} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
