"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, MapPinned, DatabaseZap, Trophy } from "lucide-react";

const NAV_ITEMS = [
  { href: "/", label: "Overview", icon: LayoutDashboard, match: (p: string) => p === "/" },
  { href: "/rankings", label: "Rankings", icon: Trophy, match: (p: string) => p.startsWith("/rankings") },
  { href: "/districts", label: "Districts", icon: MapPinned, match: (p: string) => p.startsWith("/districts") },
];

function NavList({ pathname, onNavigate }: { pathname: string; onNavigate?: () => void }) {
  return (
    <nav className="flex flex-col gap-1">
      {NAV_ITEMS.map((item) => {
        const active = item.match(pathname);
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
              active
                ? "bg-accent/10 text-accent"
                : "text-ink-secondary hover:bg-ink/5 hover:text-ink"
            }`}
          >
            <Icon size={17} strokeWidth={2} className={active ? "text-accent" : "text-ink-muted"} />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}

// Persistent left rail for md+ viewports — the "proper BI tool" shell. Below
// md, layout.tsx renders a compact horizontal top bar instead (see MobileNav).
export default function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="hidden md:flex md:w-60 md:shrink-0 md:flex-col md:border-r md:border-border md:bg-surface">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent text-white">
          <DatabaseZap size={17} strokeWidth={2} />
        </span>
        <div className="leading-tight">
          <div className="text-sm font-semibold text-ink">Bharat Expansion</div>
          <div className="text-xs text-ink-muted">Intelligence</div>
        </div>
      </div>

      <div className="flex-1 px-3">
        <NavList pathname={pathname} />
      </div>

      <div className="mx-3 mb-4 mt-4 rounded-lg border border-hairline/50 bg-page px-3 py-3">
        <div className="text-[11px] font-medium uppercase tracking-wide text-ink-muted">Data status</div>
        <div className="mt-1 text-xs text-ink-secondary">
          Opportunity Score live — 7 of 22 indicators computable this phase. See Rankings for scope notes.
        </div>
      </div>
    </aside>
  );
}

export function MobileNav() {
  const pathname = usePathname();
  return (
    <div className="border-b border-border bg-surface px-4 py-2.5 md:hidden">
      <div className="mb-2 flex items-center gap-2">
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-accent text-white">
          <DatabaseZap size={13} strokeWidth={2} />
        </span>
        <span className="text-sm font-semibold text-ink">Bharat Expansion Intelligence</span>
      </div>
      <div className="flex gap-1">
        {NAV_ITEMS.map((item) => {
          const active = item.match(pathname);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium ${
                active ? "bg-accent/10 text-accent" : "text-ink-secondary"
              }`}
            >
              <Icon size={14} strokeWidth={2} />
              {item.label}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
