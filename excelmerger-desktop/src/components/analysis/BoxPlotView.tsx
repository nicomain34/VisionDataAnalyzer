import { formatNumber } from "@/lib/utils";

type FiveNumber = {
  min?: number | null;
  p25?: number | null;
  median?: number | null;
  p75?: number | null;
  max?: number | null;
};

/** Single box-and-whisker summary rendered from already calculated statistics. */
export function BoxPlotView({ stats }: { stats: FiveNumber }) {
  const min = stats.min ?? 0;
  const max = stats.max ?? 1;
  const p25 = stats.p25 ?? min;
  const p75 = stats.p75 ?? max;
  const median = stats.median ?? (min + max) / 2;
  const span = max - min || 1;
  const pct = (v: number) => `${((v - min) / span) * 100}%`;

  return (
    <div className="flex h-full flex-col items-center justify-center px-8">
      <div className="relative h-16 w-full max-w-xl">
        <div className="absolute top-1/2 h-0.5 w-full -translate-y-1/2 bg-border" />
        <div
          className="absolute top-2 bottom-2 rounded-md border-2 border-primary bg-primary/20"
          style={{ left: pct(p25), width: `calc(${pct(p75)} - ${pct(p25)})` }}
        />
        <div className="absolute top-1 bottom-1 w-0.5 bg-warning" style={{ left: pct(median) }} />
        <div
          className="absolute top-1/2 h-3 w-0.5 -translate-y-1/2 bg-secondary"
          style={{ left: pct(min) }}
        />
        <div
          className="absolute top-1/2 h-3 w-0.5 -translate-y-1/2 bg-secondary"
          style={{ left: pct(max) }}
        />
      </div>
      <div className="mt-6 grid w-full max-w-xl grid-cols-5 gap-2 text-center text-[11px] text-secondary">
        <div>
          Min
          <div className="font-semibold text-text">{formatNumber(min)}</div>
        </div>
        <div>
          P25
          <div className="font-semibold text-text">{formatNumber(p25)}</div>
        </div>
        <div>
          Median
          <div className="font-semibold text-warning">{formatNumber(median)}</div>
        </div>
        <div>
          P75
          <div className="font-semibold text-text">{formatNumber(p75)}</div>
        </div>
        <div>
          Max
          <div className="font-semibold text-text">{formatNumber(max)}</div>
        </div>
      </div>
    </div>
  );
}

/** Horizontal mini box plot used in group/batch comparison tables. */
export function MiniBox({
  stats,
  domain,
}: {
  stats: FiveNumber;
  domain: { min: number; max: number };
}) {
  const span = domain.max - domain.min || 1;
  const pos = (v: number | null | undefined) =>
    `${Math.min(100, Math.max(0, (((v ?? domain.min) - domain.min) / span) * 100))}%`;
  return (
    <div className="relative h-4 w-full min-w-[120px]">
      <div className="absolute top-1/2 h-px w-full -translate-y-1/2 bg-border" />
      <div
        className="absolute top-1/2 h-px -translate-y-1/2 bg-secondary"
        style={{ left: pos(stats.min), width: `calc(${pos(stats.max)} - ${pos(stats.min)})` }}
      />
      <div
        className="absolute top-0.5 bottom-0.5 rounded-sm border border-primary bg-primary/25"
        style={{ left: pos(stats.p25), width: `calc(${pos(stats.p75)} - ${pos(stats.p25)})` }}
      />
      <div className="absolute top-0 bottom-0 w-0.5 bg-warning" style={{ left: pos(stats.median) }} />
    </div>
  );
}
