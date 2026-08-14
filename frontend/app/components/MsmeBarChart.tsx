"use client";

import { Bar, BarChart, CartesianGrid, Cell, Legend, ResponsiveContainer, Tooltip, TooltipContentProps, XAxis, YAxis } from "recharts";
import { AXIS_TICK_STYLE, CHART_COLORS, TOOLTIP_WRAPPER_CLASS } from "./chart-colors";

interface Msme {
  micro: number;
  small: number;
  medium: number;
  manufacturing: number;
  services: number;
}

// Two different partitions of the same Udyam population: by enterprise size
// (micro/small/medium) and by sector (manufacturing/services, derived — see
// STATUS.md item 15). They don't sum to a single shared total, so each group
// gets its own categorical color rather than implying one combined bar set.
const GROUPS: { key: keyof Msme; label: string; group: "By enterprise size" | "By sector" }[] = [
  { key: "micro", label: "Micro", group: "By enterprise size" },
  { key: "small", label: "Small", group: "By enterprise size" },
  { key: "medium", label: "Medium", group: "By enterprise size" },
  { key: "manufacturing", label: "Manufacturing", group: "By sector" },
  { key: "services", label: "Services", group: "By sector" },
];

const GROUP_COLOR: Record<string, string> = {
  "By enterprise size": CHART_COLORS.categorical[0],
  "By sector": CHART_COLORS.categorical[1],
};

function CustomTooltip({ active, payload }: TooltipContentProps) {
  if (!active || !payload || payload.length === 0) return null;
  const d = payload[0].payload as { label: string; value: number; group: string };
  return (
    <div className={TOOLTIP_WRAPPER_CLASS}>
      <div className="font-medium text-ink">{d.label}</div>
      <div className="text-ink-muted">{d.group}</div>
      <div className="mt-1 tabular-nums text-ink-secondary">{d.value.toLocaleString()} enterprises</div>
    </div>
  );
}

// Recharts 3.x derives the legend payload from chart series automatically, but this
// chart colors bars per-Cell (two logical groups, one Bar) rather than per-series —
// so we render the two group swatches directly instead of relying on auto-derivation.
function CustomLegend() {
  return (
    <ul className="mt-2 flex flex-wrap justify-center gap-4">
      {Object.entries(GROUP_COLOR).map(([group, color]) => (
        <li key={group} className="flex items-center gap-1.5 text-xs text-ink-secondary">
          <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
          {group}
        </li>
      ))}
    </ul>
  );
}

export default function MsmeBarChart({ msme }: { msme: Msme | null }) {
  if (!msme) {
    return (
      <div className="flex h-56 items-center justify-center text-sm text-ink-muted">
        No MSME data yet.
      </div>
    );
  }

  const data = GROUPS.map((g) => ({ label: g.label, group: g.group, value: msme[g.key] ?? 0 }));
  const allZero = data.every((d) => d.value === 0);

  if (allZero) {
    return (
      <div className="flex h-56 items-center justify-center text-sm text-ink-muted">
        No MSME data yet.
      </div>
    );
  }

  return (
    <div style={{ width: "100%", height: 260 }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
          <CartesianGrid vertical={false} stroke={CHART_COLORS.grid} />
          <XAxis
            dataKey="label"
            tick={AXIS_TICK_STYLE}
            axisLine={{ stroke: CHART_COLORS.axis }}
            tickLine={false}
          />
          <YAxis
            tick={AXIS_TICK_STYLE}
            axisLine={{ stroke: CHART_COLORS.axis }}
            tickLine={false}
            allowDecimals={false}
            width={48}
          />
          <Tooltip content={(props) => <CustomTooltip {...props} />} cursor={{ fill: "rgba(0,0,0,0.03)" }} />
          <Legend content={<CustomLegend />} />
          <Bar dataKey="value" radius={[4, 4, 0, 0]} maxBarSize={48}>
            {data.map((d, i) => (
              <Cell key={i} fill={GROUP_COLOR[d.group]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
