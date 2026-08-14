import type { ReactNode } from "react";

// The figure contract from the dataviz skill: label + value (+ optional hint).
// `tone` reserves the status palette for when the number genuinely means
// good/bad (e.g. quarantined rows) — never used for plain identity.
const TONE_STYLES: Record<string, { icon: string; ring: string }> = {
  default: { icon: "bg-accent/10 text-accent", ring: "" },
  warning: { icon: "bg-status-warning/15 text-[#9a6400]", ring: "" },
};

export default function StatTile({
  label,
  value,
  hint,
  icon,
  tone = "default",
  emphasis = false,
}: {
  label: string;
  value: string;
  hint?: ReactNode;
  icon: ReactNode;
  tone?: "default" | "warning";
  emphasis?: boolean;
}) {
  const toneStyle = TONE_STYLES[tone];
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <div className="flex items-center gap-2.5">
        <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${toneStyle.icon}`}>
          {icon}
        </span>
        <div className="text-xs font-medium text-ink-secondary">{label}</div>
      </div>
      <div className={`mt-3 font-semibold text-ink ${emphasis ? "text-3xl" : "text-2xl"}`}>{value}</div>
      {hint && <div className="mt-1 text-xs text-ink-muted">{hint}</div>}
    </div>
  );
}
