import { useEffect, useState } from "react";
import { buildRiskFromApiFeature, type ZoneRisk } from "@/data/zones";

interface ApiZone {
  cell_id: string;
  place_name: string;
  stress_prob: number;
  risk_level: string;
  ndvi_mean: number | null;
  precip_mm: number | null;
  temp_c: number | null;
}

let _cache: ZoneRisk[] | null = null;

const MAX_ATTEMPTS = 6;
const BASE_DELAY_MS = 3000;

async function fetchWithRetry(): Promise<ZoneRisk[]> {
  for (let n = 1; n <= MAX_ATTEMPTS; n++) {
    try {
      const r = await fetch("/api/risk");
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = (await r.json()) as { zones: ApiZone[] };
      const list = d.zones.map((z) =>
        buildRiskFromApiFeature({
          cell_id: z.cell_id,
          place_name: z.place_name,
          stress_prob: z.stress_prob,
          risk_level: z.risk_level,
          ndvi_mean: z.ndvi_mean,
          precip_mm: z.precip_mm,
          temp_c: z.temp_c,
        })
      );
      _cache = list;
      return list;
    } catch (e) {
      if (n >= MAX_ATTEMPTS) throw e;
      const delay = BASE_DELAY_MS * Math.pow(2, n - 1);
      // retry after exponential backoff
      await new Promise((res) => setTimeout(res, delay));
    }
  }
  throw new Error("Unreachable");
}

let _promise: Promise<ZoneRisk[]> | null = null;

export function useZones(): { zones: ZoneRisk[]; loading: boolean; error: string | null } {
  const [zones, setZones] = useState<ZoneRisk[]>(_cache ?? []);
  const [loading, setLoading] = useState(_cache === null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (_cache) return;
    if (!_promise) _promise = fetchWithRetry();
    _promise
      .then((list) => {
        setZones(list);
        setLoading(false);
      })
      .catch((e) => {
        setError(String(e));
        setLoading(false);
      });
  }, []);

  return { zones, loading, error };
}
