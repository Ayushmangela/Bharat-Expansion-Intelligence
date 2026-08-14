"use client";

import { useEffect, useRef, useState } from "react";
import * as echarts from "echarts";
import type { StateSummary } from "@/lib/api";

// Sequential blue ramp, light -> dark, from the dataviz skill's validated
// palette (references/palette.md) — magnitude only, never used for identity.
const SEQUENTIAL_STEPS = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#1c5cab", "#0d366b"];
const NO_DATA_FILL = "#e5e4de"; // distinct from the ramp — "not yet ingested" is a state, not a low value

function normalizeName(s: string): string {
  return s.toLowerCase().replace(/^the\s+/, "").trim();
}

function formatCount(n: number): string {
  if (n >= 100000) return `${(n / 100000).toFixed(1)}L`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return String(n);
}

interface Bin {
  min: number;
  max: number;
  color: string;
}

function buildBins(values: number[]): Bin[] {
  const sorted = [...values].sort((a, b) => a - b);
  const numBins = Math.min(SEQUENTIAL_STEPS.length, sorted.length || 1);
  const bins: Bin[] = [];
  for (let i = 0; i < numBins; i++) {
    const loIdx = Math.floor((sorted.length * i) / numBins);
    const hiIdx = Math.floor((sorted.length * (i + 1)) / numBins) - 1;
    bins.push({
      min: sorted[loIdx] ?? 0,
      max: sorted[Math.max(hiIdx, loIdx)] ?? sorted[loIdx] ?? 0,
      color: SEQUENTIAL_STEPS[i],
    });
  }
  return bins;
}

export default function StateChoropleth({ states }: { states: StateSummary[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    let disposed = false;
    let ro: ResizeObserver | null = null;

    async function setup() {
      try {
        const res = await fetch("/data/india-states.geojson");
        if (!res.ok) throw new Error(`geojson fetch failed: ${res.status}`);
        const geoJson = await res.json();
        if (disposed) return;

        // Join real company counts to geometry by normalized state name — the
        // geojson (public boundary data, pre-2019 reorg in a couple of small
        // territories) and gold.dim_geography spell a few names differently
        // ("The Dadra..." vs "Dadra...", casing on "and"). LGD codes remain the
        // real join key in the backend; this is a display-only name join for
        // rendering the shape.
        const covered = states.filter((s) => s.company_count > 0).map((s) => s.company_count);
        const bins = buildBins(covered);

        const byNormName = new Map<string, StateSummary>();
        for (const s of states) byNormName.set(normalizeName(s.state_name), s);

        const seriesData: { name: string; value: number; districts: string }[] = [];
        for (const feature of geoJson.features) {
          const geoName: string = feature.properties.st_nm;
          feature.properties.name = geoName; // echarts map series matches on `name`
          const match = byNormName.get(normalizeName(geoName));
          const count = match?.company_count ?? 0;
          seriesData.push({
            name: geoName,
            value: count,
            districts: match ? `${match.districts_with_data} of ${match.total_districts} districts` : "not yet ingested",
          });
        }

        if (!containerRef.current) return;
        echarts.registerMap("india-states", geoJson);

        // Color is driven by a piecewise visualMap (not per-item itemStyle.color —
        // that silently fails to paint on this echarts version's map series
        // renderer, confirmed by sampling canvas pixels against the internal
        // visual model: the model held the right fill color but the canvas
        // painted the series default instead). Pieces cover [bin.min, nextBin.min);
        // values below the lowest bin (i.e. the 0/no-data sentinel) fall
        // outside every piece and take outOfRange's gray.
        const pieces = bins.map((b, i) => ({
          gte: b.min,
          lt: i < bins.length - 1 ? bins[i + 1].min : undefined,
          color: b.color,
        }));

        const option = {
          tooltip: {
            trigger: "item",
            backgroundColor: "#fcfcfb",
            borderColor: "#c3c2b7",
            borderWidth: 1,
            textStyle: { color: "#0b0b0b", fontSize: 12 },
            formatter: (p: { name: string; value: number; data: { districts: string } }) =>
              `<div style="font-weight:600;margin-bottom:2px">${p.name}</div>` +
              `<div>${p.value.toLocaleString()} companies</div>` +
              `<div style="color:#898781">${p.data.districts}</div>`,
          },
          visualMap: {
            type: "piecewise",
            show: false,
            seriesIndex: 0,
            pieces,
            outOfRange: { color: NO_DATA_FILL },
          },
          series: [
            {
              type: "map",
              map: "india-states",
              roam: false,
              silent: false,
              aspectScale: 1,
              layoutCenter: ["50%", "50%"],
              layoutSize: "100%",
              itemStyle: {
                borderColor: "#fcfcfb",
                borderWidth: 1,
              },
              emphasis: {
                itemStyle: { borderColor: "#0b0b0b", borderWidth: 1.5 },
                label: { show: false },
              },
              label: { show: false },
              data: seriesData,
            },
          ],
        };

        // ECharts' map/geo projection throws a null-access TypeError if
        // setOption() runs while the container is zero-size (a real timing
        // race: a freshly-mounted flex child, or dev-mode CSS applying a beat
        // after JS runs, can both leave clientWidth/clientHeight at 0 for a
        // frame or two). Rather than trying to out-guess every cause, retry
        // init+setOption across a few animation frames until it succeeds.
        let lastErr: unknown;
        for (let attempt = 0; attempt < 30 && !disposed; attempt++) {
          const el = containerRef.current;
          if (!el) return;
          if (el.clientWidth === 0 || el.clientHeight === 0) {
            await new Promise((r) => requestAnimationFrame(r));
            continue;
          }
          try {
            const chart = echarts.init(el);
            chart.setOption(option);
            chartRef.current = chart;
            ro = new ResizeObserver(() => chart.resize());
            ro.observe(el);
            setStatus("ready");
            lastErr = undefined;
            break;
          } catch (err) {
            lastErr = err;
            chartRef.current?.dispose();
            chartRef.current = null;
            await new Promise((r) => requestAnimationFrame(r));
          }
        }
        if (lastErr && !disposed) throw lastErr;
      } catch (err) {
        if (!disposed) setStatus("error");
        console.error("StateChoropleth setup failed", err);
      }
    }

    setup();
    return () => {
      disposed = true;
      ro?.disconnect();
      chartRef.current?.dispose();
      chartRef.current = null;
    };
  }, [states]);

  const covered = states.filter((s) => s.company_count > 0).map((s) => s.company_count);
  const bins = buildBins(covered);

  if (status === "error") {
    return (
      <div className="flex h-72 items-center justify-center text-sm text-ink-muted">
        Map failed to load.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:items-center">
      <div ref={containerRef} className="h-80 w-full lg:h-96 lg:flex-1" />
      <div className="flex shrink-0 flex-row flex-wrap gap-3 lg:w-40 lg:flex-col lg:gap-2">
        {bins.map((b, i) => (
          <div key={i} className="flex items-center gap-2 text-xs text-ink-secondary">
            <span className="h-3 w-3 shrink-0 rounded-sm" style={{ backgroundColor: b.color }} />
            {i === bins.length - 1 ? `${formatCount(b.min)}+` : `${formatCount(b.min)}–${formatCount(bins[i + 1]?.min ?? b.max)}`}
          </div>
        ))}
        <div className="flex items-center gap-2 text-xs text-ink-secondary">
          <span className="h-3 w-3 shrink-0 rounded-sm" style={{ backgroundColor: NO_DATA_FILL }} />
          Not yet ingested
        </div>
      </div>
    </div>
  );
}
