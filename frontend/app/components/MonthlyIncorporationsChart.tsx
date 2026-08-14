"use client";

import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, TooltipContentProps, XAxis, YAxis } from "recharts";
import { AXIS_TICK_STYLE, CHART_COLORS, TOOLTIP_WRAPPER_CLASS, formatMonthLabel } from "./chart-colors";

interface MonthlyPoint {
  month: string;
  count: number;
}

function CustomTooltip({ active, payload }: TooltipContentProps) {
  if (!active || !payload || payload.length === 0) return null;
  const d = payload[0].payload as { month: string; count: number };
  return (
    <div className={TOOLTIP_WRAPPER_CLASS}>
      <div className="font-medium text-ink">{formatMonthLabel(d.month)}</div>
      <div className="tabular-nums text-ink-secondary">{d.count.toLocaleString()} new incorporations</div>
    </div>
  );
}

// Expects chronological order (oldest to newest) — the API returns newest-first,
// so the caller reverses before passing this prop.
export default function MonthlyIncorporationsChart({ monthly }: { monthly: MonthlyPoint[] }) {
  if (!monthly || monthly.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-ink-muted">
        No monthly incorporation data yet.
      </div>
    );
  }

  return (
    <div style={{ width: "100%", height: 280 }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={monthly} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
          <defs>
            <linearGradient id="incorporationFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={CHART_COLORS.sequentialFill} stopOpacity={0.12} />
              <stop offset="100%" stopColor={CHART_COLORS.sequentialFill} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke={CHART_COLORS.grid} />
          <XAxis
            dataKey="month"
            tickFormatter={formatMonthLabel}
            tick={AXIS_TICK_STYLE}
            axisLine={{ stroke: CHART_COLORS.axis }}
            tickLine={false}
            minTickGap={24}
          />
          <YAxis
            tick={AXIS_TICK_STYLE}
            axisLine={{ stroke: CHART_COLORS.axis }}
            tickLine={false}
            allowDecimals={false}
            width={48}
          />
          <Tooltip content={(props) => <CustomTooltip {...props} />} cursor={{ stroke: CHART_COLORS.axis, strokeWidth: 1 }} />
          <Area
            type="monotone"
            dataKey="count"
            stroke={CHART_COLORS.sequential}
            strokeWidth={2}
            fill="url(#incorporationFill)"
            dot={{ r: 3, fill: CHART_COLORS.sequential, strokeWidth: 2, stroke: "#ffffff" }}
            activeDot={{ r: 5, strokeWidth: 2, stroke: "#ffffff" }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
