import { Brain, Database, Quote, Satellite } from "lucide-react";

export default function About() {
  return (
    <div className="px-6 lg:px-10 py-12 lg:py-16 max-w-[1100px] mx-auto space-y-20">
      {/* Hero */}
      <section className="space-y-3">
        <p className="text-[11px] uppercase tracking-[0.22em] text-sand font-semibold">About the project</p>
        <h1 className="font-display text-4xl lg:text-5xl font-semibold leading-[1.05] text-balance max-w-3xl">
          We don't fear bad news.<br />
          <span className="text-sand">We fear late news.</span>
        </h1>
        <p className="text-muted-foreground max-w-2xl text-[15px] leading-relaxed">
          GaiaMind-Med is a satellite-driven early-warning system that flags vegetation stress two months
          before farmers can see it on the leaves.
        </p>
      </section>

      {/* The problem */}
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-start">
        <div className="lg:col-span-5 relative">
          <Quote className="w-8 h-8 text-terracotta mb-3" />
          <blockquote className="font-display text-xl lg:text-[22px] leading-snug text-balance">
            "We don't fear bad news. We fear late news. Once the leaves turn pale, you've already
            lost money."
          </blockquote>
          <footer className="mt-4 text-[13px] text-muted-foreground">
            <span className="font-semibold text-foreground">Juan Manuel Ortega</span>
            <br />
            Strawberry farmer · Rociana del Condado, Huelva
          </footer>
        </div>
        <div className="lg:col-span-7 space-y-4 lg:pt-2">
          <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground font-semibold">
            The problem
          </p>
          <h2 className="font-display text-2xl lg:text-3xl font-semibold leading-tight text-balance">
            Andalusian smallholders are losing crops to droughts they can't see coming.
          </h2>
          <p className="text-muted-foreground text-[15px] leading-relaxed">
            Chronic drought, shrinking water quotas and increasingly volatile rainfall have turned
            decision-making reactive. By the time foliage shows visible stress, irrigation has already
            been mistimed and yield losses of 25–30% are baked in. Existing tools either come from
            insurance companies after the harvest, or from research papers two years late.
          </p>
        </div>
      </section>

      {/* How it works */}
      <section className="space-y-8">
        <header className="space-y-2">
          <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground font-semibold">
            How it works
          </p>
          <h2 className="font-display text-2xl lg:text-3xl font-semibold leading-tight">
            From satellite pixel to actionable risk score.
          </h2>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          <Step
            n="01"
            icon={<Satellite className="w-5 h-5" />}
            title="Satellite ingestion"
            body="NDVI, land surface temperature, precipitation and soil moisture pulled at 5 km resolution from MODIS, ERA5 and CHIRPS via Google Earth Engine."
          />
          <Step
            n="02"
            icon={<Database className="w-5 h-5" />}
            title="Per-cell anomaly detection"
            body="Each variable is z-scored against a 20-year climatology so we measure how unusual today is — not just how dry it is."
          />
          <Step
            n="03"
            icon={<Brain className="w-5 h-5" />}
            title="Two-month forecast"
            body="A gradient-boosted model trained on labeled historical stress events outputs a probability per cell, 60 days ahead."
          />
        </div>
      </section>

      {/* Footer note */}
      <section className="border-t border-border pt-8 flex flex-wrap gap-6 items-end justify-between">
        <div className="space-y-1 text-[12px] text-muted-foreground">
          <p className="font-semibold text-foreground">GaiaMind-Med · v0.4 prototype</p>
          <p>Built for smallholders in Huelva, Sevilla, Cádiz, Málaga, Córdoba, Jaén, Granada, Almería.</p>
        </div>
        <div className="text-[11px] text-muted-foreground italic max-w-sm">
          This dashboard is a research prototype. Forecasts are decision-support, not guarantees —
          ground-truth with field inspection before irrigation actions.
        </div>
      </section>
    </div>
  );
}

function Step({ n, icon, title, body }: { n: string; icon: React.ReactNode; title: string; body: string }) {
  return (
    <article className="rounded-xl border border-border bg-card/60 p-6 transition-base hover:border-sand/40 hover:bg-card/80">
      <div className="flex items-center justify-between mb-5">
        <span className="w-10 h-10 rounded-lg bg-sage/15 text-sage border border-sage/25 flex items-center justify-center">
          {icon}
        </span>
        <span className="font-display text-[11px] tracking-[0.2em] text-muted-foreground font-semibold">
          {n}
        </span>
      </div>
      <h3 className="font-display text-lg font-semibold mb-2">{title}</h3>
      <p className="text-[13.5px] text-muted-foreground leading-relaxed">{body}</p>
    </article>
  );
}
