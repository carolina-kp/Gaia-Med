import { useEffect, useMemo, useRef, useState } from "react";
import { GeoJSON, MapContainer, TileLayer, useMap } from "react-leaflet";
import L, { type LatLngBoundsExpression, type Layer, type PathOptions, type LatLngExpression } from "leaflet";
import type { Feature, FeatureCollection, Geometry } from "geojson";
import {
  buildRiskFromApiFeature, RISK_COLORS, RISK_LABEL,
  type ApiGeoProps, type RiskLevel, type ZoneRisk,
} from "@/data/zones";
import { ZoneDetailPanel } from "./ZoneDetailPanel";
import { ArrowDown, ArrowUp, Filter, Loader2 } from "lucide-react";

const MAP_CENTER: LatLngExpression = [37.3, -3.8];
const MAP_ZOOM = 8;

type FilterKey = "all" | RiskLevel;

function FlyTo({ target }: { target: { bounds: LatLngBoundsExpression } | null }) {
  const map = useMap();
  useEffect(() => {
    if (!target) return;
    map.flyToBounds(target.bounds, { padding: [40, 40], duration: 0.7, maxZoom: 11 });
  }, [target, map]);
  return null;
}

function FitBoundsOnLoad({ geo, layerRef }: {
  geo: unknown;
  layerRef: React.MutableRefObject<L.GeoJSON | null>;
}) {
  const map = useMap();
  useEffect(() => {
    if (!geo) return;
    const id = setTimeout(() => {
      if (!layerRef.current) return;
      const bounds = layerRef.current.getBounds();
      if (bounds.isValid()) map.fitBounds(bounds, { padding: [20, 20] });
    }, 100);
    return () => clearTimeout(id);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [geo]);
  return null;
}

export default function RiskMap() {
  const [filter, setFilter] = useState<FilterKey>("all");
  const [selected, setSelected] = useState<ZoneRisk | null>(null);
  const [flyTarget, setFlyTarget] = useState<{ bounds: LatLngBoundsExpression } | null>(null);
  const [geo, setGeo] = useState<FeatureCollection<Geometry, ApiGeoProps> | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const layerRef = useRef<L.GeoJSON | null>(null);

  // Fetch enriched GeoJSON from the backend API
  useEffect(() => {
    let cancelled = false;
    fetch("/api/geojson")
      .then((r) => {
        if (!r.ok) throw new Error(`Failed: ${r.status}`);
        return r.json();
      })
      .then((data: FeatureCollection<Geometry, ApiGeoProps>) => {
        if (data.features?.[0]) {
          console.log("[GaiaMed] first feature props:", data.features[0].properties);
        }
        if (!cancelled) setGeo(data);
      })
      .catch((e) => !cancelled && setLoadError(String(e)));
    return () => { cancelled = true; };
  }, []);

  // Build risk for every cell once enriched GeoJSON loads
  const zones = useMemo<ZoneRisk[]>(() => {
    if (!geo) return [];
    return geo.features.map((f) => buildRiskFromApiFeature(f.properties));
  }, [geo]);

  const zonesById = useMemo(() => {
    const m = new Map<string, ZoneRisk>();
    zones.forEach((z) => m.set(z.id, z));
    return m;
  }, [zones]);

  const stats = useMemo(() => {
    const high = zones.filter((z) => z.risk === "high").length;
    const moderate = zones.filter((z) => z.risk === "moderate").length;
    const low = zones.filter((z) => z.risk === "low").length;
    return { total: zones.length, high, moderate, low };
  }, [zones]);

  const topRisk = useMemo(
    () => [...zones].sort((a, b) => b.stressProb - a.stressProb).slice(0, 5),
    [zones]
  );

  // Style function depending on filter + selection
  const styleFor = (feature?: Feature<Geometry, ApiGeoProps>): PathOptions => {
    if (!feature) return {};
    const z = zonesById.get(feature.properties.cell_id);
    if (!z) return { stroke: false, fill: false };
    const visible = filter === "all" || z.risk === filter;
    const isSel = selected?.id === z.id;
    return {
      color: isSel ? "hsl(36 47% 75%)" : "hsl(80 8% 22%)",
      weight: isSel ? 1.4 : 0.5,
      opacity: visible ? 1 : 0.15,
      fillColor: RISK_COLORS[z.risk],
      fillOpacity: visible ? (isSel ? 0.85 : 0.6) : 0.06,
    };
  };

  // Re-apply styles when filter/selection changes
  useEffect(() => {
    layerRef.current?.setStyle(styleFor as L.StyleFunction);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter, selected, zonesById]);

  const onEachFeature = (feature: Feature<Geometry, ApiGeoProps>, layer: Layer) => {
    const z = zonesById.get(feature.properties.cell_id);
    if (!z) return;
    layer.bindTooltip(
      `<div style="min-width:140px">
        <div style="font-weight:600;font-size:12px">${z.name}</div>
        <div style="font-size:10px;color:hsl(36 12% 65%)">${z.province}</div>
        <div style="font-size:11px;margin-top:2px">Stress: <b>${Math.round(z.stressProb * 100)}%</b></div>
        <div style="font-size:10px;color:hsl(36 12% 65%)">${z.topReason}</div>
      </div>`,
      { sticky: true, direction: "top", offset: [0, -2] }
    );
    layer.on({
      click: () => {
        setSelected(z);
        const path = layer as L.Path & { getBounds?: () => L.LatLngBounds };
        const bounds = path.getBounds?.();
        if (bounds) setFlyTarget({ bounds });
      },
      mouseover: (e) => {
        const l = e.target as L.Path;
        l.setStyle({ weight: 1.5, fillOpacity: 0.85 });
      },
      mouseout: () => layerRef.current?.resetStyle(layer as L.Path),
    });
  };

  const flyToZone = (z: ZoneRisk) => {
    setSelected(z);
    // Look up the layer to get bounds
    const layer = layerRef.current;
    if (!layer) return;
    layer.eachLayer((l) => {
      const f = (l as L.Layer & { feature?: Feature<Geometry, ApiGeoProps> }).feature;
      if (f?.properties.cell_id === z.id) {
        const path = l as L.Path & { getBounds?: () => L.LatLngBounds };
        const bounds = path.getBounds?.();
        if (bounds) setFlyTarget({ bounds });
      }
    });
  };

  return (
    <div className="flex h-[calc(100vh-3.5rem)] w-full overflow-hidden">
      {/* LEFT SIDEBAR */}
      <aside className="w-[300px] shrink-0 border-r border-border bg-card/40 backdrop-blur-sm flex flex-col overflow-y-auto">
        <div className="p-4 space-y-3">
          <div>
            <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground font-semibold">
              Andalusia · Oct 2025
            </p>
            <h1 className="font-display text-lg font-semibold mt-0.5">Vegetation Risk</h1>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <StatCard label="Municipalities" value={stats.total} trend={0} accent="muted" />
            <StatCard label="High Risk" value={stats.high} trend={+8} accent="terracotta" />
            <StatCard label="Moderate" value={stats.moderate} trend={+2} accent="sand" />
            <StatCard label="Low Risk" value={stats.low} trend={-5} accent="sage" />
          </div>
        </div>

        <div className="px-4 pb-3">
          <div className="flex items-center gap-1.5 mb-2 text-[10px] uppercase tracking-[0.14em] text-muted-foreground font-semibold">
            <Filter className="w-3 h-3" /> Filter
          </div>
          <div className="grid grid-cols-4 gap-1 p-1 rounded-lg bg-background/60 border border-border">
            {(["all", "high", "moderate", "low"] as FilterKey[]).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`text-[11px] py-1.5 rounded-md font-medium capitalize transition-base ${
                  filter === f
                    ? f === "high"
                      ? "bg-terracotta text-terracotta-foreground"
                      : f === "moderate"
                      ? "bg-sand text-sand-foreground"
                      : f === "low"
                      ? "bg-sage text-sage-foreground"
                      : "bg-foreground text-background"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>

        <div className="px-4 pb-2">
          <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground font-semibold mb-2">
            Top 5 at-risk
          </p>
          <ul className="space-y-1">
            {topRisk
              .filter((z) => filter === "all" || z.risk === filter)
              .map((z) => (
                <li key={z.id}>
                  <button
                    onClick={() => flyToZone(z)}
                    className={`w-full flex items-center gap-2 px-2 py-2 rounded-md text-left transition-base hover:bg-card-elev ${
                      selected?.id === z.id ? "bg-card-elev" : ""
                    }`}
                  >
                    <RiskPill risk={z.risk} compact />
                    <div className="min-w-0 flex-1">
                      <p className="text-[12px] font-medium truncate">{z.name}</p>
                      <p className="text-[10px] text-muted-foreground truncate">{z.province}</p>
                    </div>
                    <span className="text-[12px] font-semibold tabular-nums">
                      {Math.round(z.stressProb * 100)}%
                    </span>
                  </button>
                </li>
              ))}
          </ul>
        </div>

        <div className="mt-auto p-4 border-t border-border">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground font-semibold">
                Model confidence
              </p>
              <p className="font-display text-sm font-semibold mt-0.5">Random Forest · 300 trees</p>
            </div>
            <div className="px-2.5 py-1 rounded-full bg-sage/15 text-sage text-[11px] font-semibold border border-sage/30">
              AUC 0.89
            </div>
          </div>
        </div>
      </aside>

      {/* MAP */}
      <div className="relative flex-1 min-w-0">
        <MapContainer
          center={MAP_CENTER}
          zoom={MAP_ZOOM}
          className="absolute inset-0"
          zoomControl
          attributionControl
          scrollWheelZoom
        >
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png"
            attribution='&copy; OpenStreetMap &copy; CARTO · Municipalities © IECA / opendatasoft'
            subdomains="abcd"
          />
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}{r}.png"
            subdomains="abcd"
            opacity={0.7}
          />
          {geo && (
            <GeoJSON
              key="muni"
              data={geo}
              style={styleFor as L.StyleFunction}
              onEachFeature={onEachFeature}
              ref={(r) => {
                layerRef.current = r as unknown as L.GeoJSON;
              }}
            />
          )}
          <FlyTo target={flyTarget} />
          <FitBoundsOnLoad geo={geo} layerRef={layerRef} />
        </MapContainer>

        {/* Loading / error overlays */}
        {!geo && !loadError && (
          <div className="absolute inset-0 z-[400] flex items-center justify-center bg-background/40 backdrop-blur-sm">
            <div className="flex items-center gap-2 px-4 py-2 rounded-full glass-card text-[12px] text-muted-foreground">
              <Loader2 className="w-4 h-4 animate-spin text-sand" />
              Loading Andalusia municipalities…
            </div>
          </div>
        )}
        {loadError && (
          <div className="absolute inset-0 z-[400] flex items-center justify-center">
            <div className="px-4 py-3 rounded-lg border border-terracotta/40 bg-card text-[12px] text-terracotta max-w-sm text-center">
              Failed to load polygons. {loadError}
            </div>
          </div>
        )}

        {/* Map legend */}
        <div className="absolute left-4 bottom-4 z-[400] glass-card rounded-lg px-3 py-2 text-[11px]">
          <p className="text-[9px] uppercase tracking-[0.14em] text-muted-foreground font-semibold mb-1.5">
            Stress probability · Oct 2025
          </p>
          <div className="flex items-center gap-3">
            <LegendSwatch color="hsl(var(--sage))" label="Low" />
            <LegendSwatch color="hsl(var(--sand))" label="Moderate" />
            <LegendSwatch color="hsl(var(--terracotta))" label="High" />
          </div>
        </div>

        {/* Detail panel */}
        {selected && (
          <ZoneDetailPanel zone={selected} onClose={() => setSelected(null)} />
        )}
      </div>
    </div>
  );
}

function StatCard({
  label, value, trend, accent,
}: { label: string; value: number; trend: number; accent: "terracotta" | "sand" | "sage" | "muted" }) {
  const accentClass =
    accent === "terracotta" ? "text-terracotta"
    : accent === "sand" ? "text-sand"
    : accent === "sage" ? "text-sage"
    : "text-foreground";
  return (
    <div className="rounded-lg border border-border bg-card/70 p-2.5">
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">{label}</p>
      <div className="flex items-end justify-between mt-1">
        <span className={`font-display text-xl font-semibold tabular-nums ${accentClass}`}>{value}</span>
        {trend !== 0 && (
          <span className={`flex items-center text-[10px] tabular-nums ${trend > 0 ? "text-terracotta" : "text-sage"}`}>
            {trend > 0 ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />}
            {Math.abs(trend)}%
          </span>
        )}
      </div>
    </div>
  );
}

function RiskPill({ risk, compact = false }: { risk: RiskLevel; compact?: boolean }) {
  const cls =
    risk === "high" ? "bg-terracotta/20 text-terracotta border-terracotta/40"
    : risk === "moderate" ? "bg-sand/20 text-sand border-sand/40"
    : "bg-sage/20 text-sage border-sage/40";
  return (
    <span className={`inline-flex items-center gap-1 border rounded-full ${compact ? "px-1.5 py-0.5 text-[9px]" : "px-2 py-0.5 text-[11px]"} font-semibold ${cls}`}>
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: RISK_COLORS[risk] }} />
      {RISK_LABEL[risk]}
    </span>
  );
}

function LegendSwatch({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="w-3 h-3 rounded-sm border border-border" style={{ background: color }} />
      <span className="text-foreground/80">{label}</span>
    </div>
  );
}
