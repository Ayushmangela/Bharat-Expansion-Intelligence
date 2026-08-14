import type { ReactNode } from "react";

// The one card shell every panel on every page uses — this is what makes the
// three pages read as one system instead of a stack of separately-styled
// widgets (dataviz skill: shared card styling, spacing, and color usage).
export default function Card({
  title,
  subtitle,
  action,
  padded = true,
  className = "",
  children,
}: {
  title?: string;
  subtitle?: ReactNode;
  action?: ReactNode;
  padded?: boolean;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div
      className={`rounded-xl border border-border bg-surface shadow-[0_1px_2px_rgba(11,11,11,0.04)] ${className}`}
    >
      {(title || action) && (
        <div className="flex items-start justify-between gap-4 border-b border-hairline/40 px-5 py-4">
          <div>
            {title && <h2 className="text-sm font-semibold text-ink">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-xs text-ink-secondary">{subtitle}</p>}
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </div>
      )}
      <div className={padded ? "p-5" : ""}>{children}</div>
    </div>
  );
}
