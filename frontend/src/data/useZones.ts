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
let _promise: Promise<ZoneRisk[]> | null = null;

export function useZones(): { zones: ZoneRisk[]; loading: boolean; error: string | null } {
  const [zones, setZones] = useState<ZoneRisk[]>(_cache ?? []);
  const [loading, setLoading] = useState(_cache === null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (_cache) return;
    if (!_promise) {
      _promise = fetch("/api/risk")
        .then((r) => {
          if (!r.ok) throw new Error(`Failed: ${r.status}`);
          return r.json() as Promise<{ zones: ApiZone[] }>;
        })
        .then((d) => {
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
        });
    }
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
