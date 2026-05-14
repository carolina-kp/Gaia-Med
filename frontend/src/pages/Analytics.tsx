import {
  Area, CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis, BarChart, Bar, Cell, LabelList,
} from "recharts";
import { useEffect, useMemo, useState } from "react";
import { useZones } from "@/data/useZones";
import { Calendar, Database, Satellite, Sprout, Thermometer } from "lucide-react";

interface TimeseriesPoint {
  month: string;
  observed: number;
  predicted: number;
}

const features = [
  { name: "NDVI 30d trend",         importance: 22.4, type: "vegetation" },
  { name: "NDVI seasonal anomaly",  importance: 18.1, type: "vegetation" },
  { name: "Cumulative rainfall 90d",importance: 14.6, type: "climate" },
  { name: "Soil moisture anomaly",  importance: 11.2, type: "climate" },
  { name: "LST anomaly 30d",        importance:  9.8, type: "temperature" },
  { name: "Heat-degree days",       importance:  7.5, type: "temperature" },
  { name: "Rainfall variability",   importance:  6.4, type: "climate" },
  { name: "EVI departure",          importance:  5.1, type: "vegetation" },
  { name: "Lat / elevation",        importance:  4.9, type: "climate" },
];
const FEATURE_COLORS: Record<string, string> = {
  vegetation: "hsl(var(--sage))",
  climate: "hsl(var(--sand))",
  temperature: "hsl(var(--terracotta))",
};

export default function Analytics() {
  const { zones, loading } = useZones();
  const [evolution, setEvolution] = useState<TimeseriesPoint[]>([]);

  useEffect(() => {
    fetch("https://Pochemucka-gaiamed-backend.hf.space/api/timeseries")
      .then((r) => r.json())
      .then((d: { months: string[]; observed: number[]; predicted: number[] }) => {
        setEvolution(
          d.months.map((m, i) => ({
            month: m,
            observed: d.observed[i],
            predicted: d.predicted[i],
          }))
        );
      })
      .catch(() => {});
  }, []);

  // Histogram of stress probability across zones
  const histogram = useMemo(() => {
    const bins = Array.from({ length: 20 }, (_, i) => ({
      x: i * 5,
      label: `${i * 5}–${i * 5 + 5}`,
      count: 0,
      band: i * 5 < 33 ? "low" : i * 5 < 66 ? "moderate" : "high",
    }));
    zones.forEach((z) => {
      const idx = Math.min(19, Math.floor(z.stressProb * 20));
      bins[idx].count++;
    });
    return bins;
  }, [zones]);

  const totalZones = zones.length;

  return (
    <div className="px-6 lg:px-10 py-8 max-w-[1500px] mx-auto space-y-6">
      <header className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground font-semibold">
            Model intelligence
          </p>
          <h1 className="font-display text-2xl lg:text-3xl font-semibold mt-1">Analytics</h1>
          <p className="text-sm text-muted-foreground mt-1 max-w-xl">
            How the GaiaMind-Med forecaster is performing across {loading ? "…" : totalZones} municipalities in Andalusia.
          </p>
        </div>
        <div className="flex gap-2 text-[11px]">
          <Tag>March 2024 → Oct 2025</Tag>
          <Tag accent>Updated 6 hours ago</Tag>
        </div>
      </header>

      {/* Row 1 — Time evolution */}
      <Panel
        title="Observed vs predicted stress fraction"
        subtitle="Share of Andalusian cells flagged as stressed each month — last 8 months."
      >
        <div className="h-[280px]">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={evolution} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="predFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="hsl(var(--terracotta))" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="hsl(var(--terracotta))" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="2 4" vertical={false} />
              <XAxis dataKey="month" stroke="hsl(var(--muted-foreground))" fontSize={11} tickLine={false} axisLine={{ stroke: "hsl(var(--border))" }} />
              <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} tickLine={false} axisLine={{ stroke: "hsl(var(--border))" }} tickFormatter={(v) => `${Math.round(v * 100)}%`} domain={[0, 0.6]} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} iconType="line" />
<Area type="monotone" dataKey="predicted" stroke="none" fill="url(#predFill)" name="Predicted (area)" legendType="none" />
              <Line type="monotone" dataKey="observed" stroke="hsl(var(--sage))" strokeWidth={2.2} dot={{ r: 3, fill: "hsl(var(--sage))" }} name="Observed" connectNulls={false} />
              <Line type="monotone" dataKey="predicted" stroke="hsl(var(--terracotta))" strokeWidth={2.2} strokeDasharray="0" dot={{ r: 3, fill: "hsl(var(--terracotta))" }} name="Predicted" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </Panel>

      {/* Row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Panel title="Feature importance" subtitle="Variables driving the forecast (Random Forest importance, normalized).">
          <div className="h-[320px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={features} layout="vertical" margin={{ top: 4, right: 40, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="2 4" horizontal={false} />
                <XAxis type="number" stroke="hsl(var(--muted-foreground))" fontSize={11} tickLine={false} axisLine={false} tickFormatter={(v) => `${v}%`} />
                <YAxis type="category" dataKey="name" stroke="hsl(var(--muted-foreground))" fontSize={11} width={150} tickLine={false} axisLine={false} />
                <Tooltip content={<CustomTooltip suffix="%" />} cursor={{ fill: "hsl(var(--muted) / 0.4)" }} />
                <Bar dataKey="importance" radius={[0, 4, 4, 0]} barSize={16}>
                  {features.map((f, i) => (
                    <Cell key={i} fill={FEATURE_COLORS[f.type]} />
                  ))}
                  <LabelList dataKey="importance" position="right" fill="hsl(var(--muted-foreground))" fontSize={10} formatter={(v: number) => `${v.toFixed(1)}%`} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="flex items-center gap-4 mt-2 text-[11px] text-muted-foreground">
            <Dot color="hsl(var(--sage))" /> Vegetation
            <Dot color="hsl(var(--sand))" /> Climate
            <Dot color="hsl(var(--terracotta))" /> Temperature
          </div>
        </Panel>

        <Panel title="Stress probability distribution" subtitle={`All ${totalZones || "…"} municipalities, October 2025 forecast.`}>
          <div className="h-[320px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={histogram} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="2 4" vertical={false} />
                <XAxis dataKey="x" stroke="hsl(var(--muted-foreground))" fontSize={10} tickLine={false} axisLine={{ stroke: "hsl(var(--border))" }} tickFormatter={(v) => `${v}%`} />
                <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} tickLine={false} axisLine={false} />
                <Tooltip content={<CustomTooltip suffix=" cells" labelKey="label" labelPrefix="Stress " />} cursor={{ fill: "hsl(var(--muted) / 0.4)" }} />
                <Bar dataKey="count" radius={[3, 3, 0, 0]}>
                  {histogram.map((b, i) => (
                    <Cell
                      key={i}
                      fill={
                        b.band === "high" ? "hsl(var(--terracotta))"
                        : b.band === "moderate" ? "hsl(var(--sand))"
                        : "hsl(var(--sage))"
                      }
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="flex items-center gap-4 mt-2 text-[11px] text-muted-foreground">
            <Dot color="hsl(var(--sage))" /> Low &lt;33%
            <Dot color="hsl(var(--sand))" /> Moderate 33–66%
            <Dot color="hsl(var(--terracotta))" /> High &gt;66%
          </div>
        </Panel>
      </div>

      {/* Row 3 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Panel title="Model performance" subtitle="Held-out test set, stratified by province.">
          <div className="grid grid-cols-2 gap-3">
            <Metric label="Test accuracy" value="84.6%" />
            <Metric label="ROC-AUC" value="0.89" accent />
            <Metric label="Precision (high)" value="81%" />
            <Metric label="Recall (high)" value="78%" />
          </div>
          <div className="mt-4 pt-3 border-t border-border text-[11.5px] text-muted-foreground space-y-1">
            <p>Trained: Mar 2024 – Mar 2025</p>
            <p>Tested: Apr 2025 – Sep 2025</p>
            <p>Algorithm: Random Forest · 300 trees · balanced weights</p>
          </div>
        </Panel>

        <Panel title="Data coverage">
          <ul className="space-y-3.5">
            <CoverageRow icon={<Sprout className="w-4 h-4" />} label="Municipalities" value={totalZones ? String(totalZones) : "…"} sub="real INE polygons" />
            <CoverageRow icon={<Calendar className="w-4 h-4" />} label="Time window" value="20 months" sub="rolling" />
            <CoverageRow icon={<Satellite className="w-4 h-4" />} label="Satellite variables" value="4" sub="NDVI · LST · precip · soil moisture" />
            <CoverageRow icon={<Database className="w-4 h-4" />} label="Bounds" value="36.0–38.7°N · 7.5–1.6°W" sub="Andalusia" />
          </ul>
        </Panel>

        <Panel title="Prediction horizon" subtitle="We forecast 2 months ahead.">
          <Horizon />
          <p className="text-[12px] text-muted-foreground mt-3 leading-relaxed">
            Using vegetation, rainfall and temperature signals from the last 90 days, we estimate stress
            probability for each cell <span className="text-foreground font-medium">+60 days</span> into the future.
          </p>
        </Panel>
      </div>
    </div>
  );
}

function Panel({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-border bg-card/70 p-5 backdrop-blur-sm">
      <header className="mb-4">
        <h2 className="font-display text-base font-semibold">{title}</h2>
        {subtitle && <p className="text-[12.5px] text-muted-foreground mt-0.5">{subtitle}</p>}
      </header>
      {children}
    </section>
  );
}

function Tag({ children, accent = false }: { children: React.ReactNode; accent?: boolean }) {
  return (
    <span className={`px-2.5 py-1 rounded-full border ${accent ? "border-sage/40 bg-sage/15 text-sage" : "border-border bg-card text-muted-foreground"} font-medium`}>
      {children}
    </span>
  );
}

function Metric({ label, value, accent = false }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="rounded-lg bg-background/60 border border-border p-3">
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">{label}</p>
      <p className={`font-display text-xl font-semibold mt-1 tabular-nums ${accent ? "text-sand" : ""}`}>{value}</p>
    </div>
  );
}

function CoverageRow({ icon, label, value, sub }: { icon: React.ReactNode; label: string; value: string; sub?: string }) {
  return (
    <li className="flex items-center gap-3">
      <span className="w-9 h-9 rounded-lg bg-background/60 border border-border flex items-center justify-center text-sage shrink-0">
        {icon}
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">{label}</p>
        <p className="text-[14px] font-semibold leading-tight">{value}</p>
        {sub && <p className="text-[11px] text-muted-foreground">{sub}</p>}
      </div>
    </li>
  );
}

function Horizon() {
  return (
    <div className="mt-1">
      <div className="relative h-12">
        <div className="absolute top-1/2 left-0 right-0 h-0.5 bg-border" />
        <div className="absolute top-1/2 left-[10%] w-[55%] h-0.5 bg-sand" />
        <div className="absolute top-1/2 left-[10%] -translate-y-1/2">
          <Marker label="Today" sublabel="Aug 2025" color="hsl(var(--sage))" />
        </div>
        <div className="absolute top-1/2 left-[65%] -translate-y-1/2">
          <Marker label="Forecast" sublabel="Oct 2025" color="hsl(var(--terracotta))" pulse />
        </div>
      </div>
      <div className="flex items-center justify-center gap-1.5 mt-2 text-[11px] text-sand font-medium">
        <Thermometer className="w-3 h-3" /> +60 day window
      </div>
    </div>
  );
}

function Marker({ label, sublabel, color, pulse }: { label: string; sublabel: string; color: string; pulse?: boolean }) {
  return (
    <div className="flex flex-col items-center -translate-x-1/2">
      <span className="relative w-3 h-3 rounded-full" style={{ background: color }}>
        {pulse && <span className="absolute inset-0 rounded-full pulse-dot" style={{ background: color, opacity: 0.5 }} />}
      </span>
      <span className="mt-1 text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">{label}</span>
      <span className="text-[11px] font-semibold" style={{ color }}>{sublabel}</span>
    </div>
  );
}

function CustomTooltip({
  active, payload, label, suffix = "", labelKey, labelPrefix = "",
}: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string; payload: Record<string, unknown> }>;
  label?: string | number;
  suffix?: string;
  labelKey?: string;
  labelPrefix?: string;
}) {
  if (!active || !payload?.length) return null;
  const displayLabel = labelKey && payload[0]?.payload ? (payload[0].payload[labelKey] as string) : label;
  return (
    <div className="rounded-md border border-border bg-card/95 backdrop-blur px-2.5 py-2 text-[11px] shadow-xl">
      <p className="text-muted-foreground mb-1">{labelPrefix}{displayLabel}</p>
      {payload.map((p, i) => (
        <div key={i} className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full" style={{ background: p.color }} />
          <span className="text-foreground/90">{p.name}:</span>
          <span className="font-semibold tabular-nums">
            {typeof p.value === "number" && p.value < 1 && suffix === ""
              ? `${(p.value * 100).toFixed(1)}%`
              : `${p.value}${suffix}`}
          </span>
        </div>
      ))}
    </div>
  );
}

function Dot({ color }: { color: string }) {
  return <span className="inline-block w-2 h-2 rounded-full mr-1" style={{ background: color }} />;
}
