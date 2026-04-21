import { X } from "lucide-react";
import type { ZoneRisk } from "@/data/zones";
import { RISK_COLORS, RISK_LABEL } from "@/data/zones";

interface Props {
  zone: ZoneRisk;
  onClose: () => void;
}

export function ZoneDetailPanel({ zone, onClose }: Props) {
  const pct = Math.round(zone.stressProb * 100);
  const ndviPct = Math.round(Math.abs(zone.ndviAnomaly) * 100);
  const rainPct = Math.round((Math.abs(zone.rainfallAnomaly) / 80) * 100);

  return (
    <aside className="absolute top-0 right-0 bottom-0 w-[320px] z-[500] border-l border-border bg-card/95 backdrop-blur-md animate-slide-in-right overflow-y-auto">
      <button
        onClick={onClose}
        className="absolute top-3 right-3 w-7 h-7 rounded-md flex items-center justify-center text-muted-foreground hover:bg-card-elev hover:text-foreground transition-base"
        aria-label="Close panel"
      >
        <X className="w-4 h-4" />
      </button>

      <div className="p-5 space-y-5">
        <div>
          <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground font-semibold">
            {zone.province}
          </p>
          <h2 className="font-display text-lg font-semibold mt-0.5 leading-tight pr-8">
            {zone.name}
          </h2>
          <div className="mt-2">
            <RiskBadge risk={zone.risk} />
          </div>
        </div>

        {/* Gauge */}
        <Gauge value={zone.stressProb} risk={zone.risk} />

        {/* Factor bars */}
        <div className="space-y-3">
          <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground font-semibold">
            Contributing factors
          </p>
          <FactorBar
            label="NDVI anomaly"
            value={`${zone.ndviAnomaly > 0 ? "+" : ""}${zone.ndviAnomaly.toFixed(2)}`}
            pct={Math.min(100, ndviPct * 1.4)}
            color="hsl(var(--sage))"
          />
          <FactorBar
            label="Rainfall anomaly"
            value={`${zone.rainfallAnomaly > 0 ? "+" : ""}${zone.rainfallAnomaly.toFixed(0)} mm`}
            pct={Math.min(100, rainPct)}
            color="hsl(var(--sand))"
          />
          <FactorBar
            label="Temperature anomaly"
            value={`${zone.tempAnomaly > 0 ? "+" : ""}${zone.tempAnomaly.toFixed(1)} °C`}
            pct={Math.min(100, Math.abs(zone.tempAnomaly) * 25)}
            color="hsl(var(--terracotta))"
          />
        </div>

        {/* Explanation */}
        <div className="rounded-lg border border-border bg-background/50 p-3.5 text-[12.5px] leading-relaxed">
          <p className="text-foreground/90">
            This zone is flagged because vegetation health is{" "}
            <span className="font-semibold text-sage">{ndviPct}% below</span> the seasonal average and rainfall has been{" "}
            <span className="font-semibold text-sand">
              {Math.round((Math.abs(zone.rainfallAnomaly) / 80) * 100)}% lower
            </span>{" "}
            than normal for {zone.province}.
          </p>
        </div>

        <div className="rounded-lg border border-terracotta/30 bg-terracotta/10 p-3.5">
          <p className="text-[10px] uppercase tracking-[0.14em] text-terracotta font-semibold mb-1">
            Why this matters
          </p>
          <p className="text-[12.5px] leading-relaxed text-foreground/90">
            Conditions like these preceded yield losses of <span className="font-semibold">25–30%</span> in the
            2022 and 2023 seasons across {zone.province} smallholdings.
          </p>
        </div>

        <div className="pt-2 border-t border-border text-[11px] text-muted-foreground flex justify-between">
          <span>Cell ID</span>
          <span className="font-mono">{zone.id}</span>
        </div>
      </div>
    </aside>
  );
}

function RiskBadge({ risk }: { risk: ZoneRisk["risk"] }) {
  const cls =
    risk === "high" ? "bg-terracotta text-terracotta-foreground"
    : risk === "moderate" ? "bg-sand text-sand-foreground"
    : "bg-sage text-sage-foreground";
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold ${cls}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current opacity-80" />
      {RISK_LABEL[risk]} risk
    </span>
  );
}

function Gauge({ value, risk }: { value: number; risk: ZoneRisk["risk"] }) {
  const pct = Math.round(value * 100);
  const radius = 70;
  const circ = Math.PI * radius; // half circle
  const offset = circ * (1 - value);
  const color = RISK_COLORS[risk];

  return (
    <div className="relative flex flex-col items-center pt-1">
      <svg width="200" height="120" viewBox="0 0 200 120" className="overflow-visible">
        <defs>
          <linearGradient id="gauge-grad" x1="0" x2="1">
            <stop offset="0%" stopColor="hsl(var(--sage))" />
            <stop offset="50%" stopColor="hsl(var(--sand))" />
            <stop offset="100%" stopColor="hsl(var(--terracotta))" />
          </linearGradient>
        </defs>
        <path
          d="M 20 100 A 80 80 0 0 1 180 100"
          fill="none"
          stroke="hsl(var(--border))"
          strokeWidth="14"
          strokeLinecap="round"
        />
        <path
          d="M 20 100 A 80 80 0 0 1 180 100"
          fill="none"
          stroke="url(#gauge-grad)"
          strokeWidth="14"
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 600ms ease" }}
          opacity="0.95"
        />
      </svg>
      <div className="-mt-14 text-center">
        <p className="font-display text-4xl font-semibold tabular-nums" style={{ color }}>{pct}%</p>
        <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground font-semibold mt-0.5">
          Stress probability
        </p>
      </div>
    </div>
  );
}

function FactorBar({ label, value, pct, color }: { label: string; value: string; pct: number; color: string }) {
  return (
    <div>
      <div className="flex items-center justify-between text-[12px] mb-1">
        <span className="text-foreground/85">{label}</span>
        <span className="font-semibold tabular-nums" style={{ color }}>{value}</span>
      </div>
      <div className="h-1.5 rounded-full bg-background/70 overflow-hidden">
        <div
          className="h-full rounded-full transition-base"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
    </div>
  );
}
