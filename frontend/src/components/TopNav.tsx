import { Link, useLocation } from "react-router-dom";
import { Leaf } from "lucide-react";

const NAV = [
  { to: "/", label: "Risk Map" },
  { to: "/analytics", label: "Analytics" },
  { to: "/about", label: "About" },
];

export function TopNav() {
  const { pathname } = useLocation();
  return (
    <header className="sticky top-0 z-40 border-b border-border/70 bg-background/80 backdrop-blur-md">
      <div className="flex h-14 items-center px-5 gap-8">
        <Link to="/" className="flex items-center gap-2.5 group">
          <BrandMark />
          <span className="font-display font-semibold tracking-tight text-[15px]">
            GaiaMind<span className="text-sand">-Med</span>
          </span>
        </Link>

        <nav className="flex items-center gap-1">
          {NAV.map((n) => {
            const active = pathname === n.to;
            return (
              <Link
                key={n.to}
                to={n.to}
                className={`relative px-3 py-1.5 text-[13px] font-medium rounded-md transition-base ${
                  active
                    ? "text-foreground bg-card-elev"
                    : "text-muted-foreground hover:text-foreground hover:bg-card/60"
                }`}
              >
                {n.label}
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto flex items-center gap-3">
          <div className="hidden sm:flex items-center gap-2 px-2.5 py-1 rounded-full border border-terracotta/40 bg-terracotta/10 text-terracotta text-[11px] font-medium tracking-wide">
            <span className="w-1.5 h-1.5 rounded-full bg-terracotta" />
            Predicting: Oct 2025
          </div>
          <div className="flex items-center gap-2 px-2.5 py-1 rounded-full border border-border bg-card/50 text-[11px] font-medium">
            <span className="relative inline-flex w-2 h-2">
              <span className="absolute inset-0 rounded-full bg-live pulse-dot" />
              <span className="relative w-2 h-2 rounded-full bg-live" />
            </span>
            <span className="text-muted-foreground">Live</span>
          </div>
        </div>
      </div>
    </header>
  );
}

function BrandMark() {
  return (
    <svg width="24" height="24" viewBox="0 0 32 32" fill="none" className="transition-base group-hover:rotate-[-6deg]">
      {/* leaf */}
      <path
        d="M6 24 C 8 12, 18 6, 26 6 C 26 16, 20 24, 8 26 Z"
        fill="hsl(var(--sage))"
        opacity="0.95"
      />
      <path d="M7 25 C 12 18, 18 12, 25 8" stroke="hsl(var(--olive))" strokeWidth="1.2" strokeLinecap="round" />
      {/* satellite */}
      <g transform="translate(20 4)">
        <rect x="-2" y="-2" width="4" height="4" rx="0.6" fill="hsl(var(--sand))" />
        <rect x="-6" y="-1" width="3.4" height="2" fill="hsl(var(--sand))" opacity="0.7" />
        <rect x="2.6" y="-1" width="3.4" height="2" fill="hsl(var(--sand))" opacity="0.7" />
        <circle cx="0" cy="-4.5" r="0.8" fill="hsl(var(--terracotta))" />
      </g>
    </svg>
  );
}
