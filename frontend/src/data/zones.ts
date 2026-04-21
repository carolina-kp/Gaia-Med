export type RiskLevel = "high" | "moderate" | "low";

export interface MunicipalityProps {
  id: string;        // INE municipality code
  name: string;
  province: string;
}

export interface ZoneRisk {
  id: string;
  name: string;
  province: string;
  stressProb: number;
  risk: RiskLevel;
  ndviAnomaly: number;
  rainfallAnomaly: number;
  tempAnomaly: number;
  topReason: string;
  center?: [number, number]; // [lat, lng]
}

const PROVINCE_BIAS: Record<string, number> = {
  "Almería": 0.70,
  "Jaén":    0.60,
  "Córdoba": 0.55,
  "Huelva":  0.55,
  "Granada": 0.50,
  "Málaga":  0.50,
  "Sevilla": 0.45,
  "Cádiz":   0.40,
};

const REASONS = [
  "Severe rainfall deficit",
  "Persistent NDVI anomaly",
  "Heat-stress accumulation",
  "Soil moisture collapse",
  "Late-season dry spell",
  "Compound drought + heat",
];

function hashStr(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0) / 4294967296;
}

function classify(p: number): RiskLevel {
  if (p >= 0.66) return "high";
  if (p >= 0.33) return "moderate";
  return "low";
}

export function buildRisk(props: MunicipalityProps): ZoneRisk {
  const bias = PROVINCE_BIAS[props.province] ?? 0.5;
  const r1 = hashStr(props.id);
  const r2 = hashStr(props.id + "x");
  const r3 = hashStr(props.id + "y");
  const r4 = hashStr(props.id + "z");

  const jitter = (r1 - 0.5) * 0.45;
  let stress = bias + jitter;
  stress = Math.max(0.04, Math.min(0.97, stress));

  const ndvi = -((stress - 0.3) * 0.4 + (r2 - 0.5) * 0.08);
  const rain = -((stress - 0.3) * 70 + (r3 - 0.5) * 25);
  const temp = (stress - 0.3) * 3.5 + (r4 - 0.5) * 0.9;

  return {
    id: props.id,
    name: props.name,
    province: props.province,
    stressProb: stress,
    risk: classify(stress),
    ndviAnomaly: +ndvi.toFixed(3),
    rainfallAnomaly: +rain.toFixed(1),
    tempAnomaly: +temp.toFixed(2),
    topReason: REASONS[Math.floor(r1 * REASONS.length)],
  };
}

export const RISK_COLORS: Record<RiskLevel, string> = {
  high: "#C4622D",
  moderate: "#C8A96E",
  low: "#7A9E7E",
};

export const RISK_LABEL: Record<RiskLevel, string> = {
  high: "High",
  moderate: "Moderate",
  low: "Low",
};

// ── API types (backend /api/geojson and /api/risk) ──────────────────────────

export interface ApiGeoProps {
  cell_id: string;
  place_name: string;
  stress_prob: number;
  risk_level: string;
  ndvi_mean: number | null;
  precip_mm: number | null;
  temp_c: number | null;
  [key: string]: unknown;
}

const API_REASONS: Record<RiskLevel, string> = {
  high: "Compound drought + heat",
  moderate: "Persistent NDVI anomaly",
  low: "Within seasonal norms",
};

function classifyProb(p: number): RiskLevel {
  if (p >= 0.65) return "high";
  if (p >= 0.35) return "moderate";
  return "low";
}

export function buildRiskFromApiFeature(props: ApiGeoProps): ZoneRisk {
  const prob = typeof props.stress_prob === "number" ? props.stress_prob : 0;
  const validLevels: RiskLevel[] = ["high", "moderate", "low"];
  const risk: RiskLevel =
    props.risk_level && validLevels.includes(props.risk_level as RiskLevel)
      ? (props.risk_level as RiskLevel)
      : classifyProb(prob);
  return {
    id: props.cell_id,
    name: props.place_name ?? `Zone ${props.cell_id}`,
    province: "",
    stressProb: prob,
    risk,
    ndviAnomaly: props.ndvi_mean ?? 0,
    rainfallAnomaly: props.precip_mm ?? 0,
    tempAnomaly: props.temp_c ?? 0,
    topReason: API_REASONS[risk],
  };
}
