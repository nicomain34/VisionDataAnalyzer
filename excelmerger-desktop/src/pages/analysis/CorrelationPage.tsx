import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Play } from "lucide-react";
import { PageHeader } from "@/components/ui/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { DatasetBar, AnalysisGate } from "@/components/analysis/DatasetBar";
import {
  ExportBar,
  Field,
  InsightList,
  SectionCard,
  Select,
} from "@/components/analysis/Controls";
import { useI18n } from "@/lib/i18n";
import { useAnalysisCall, useSession } from "@/lib/analysisSession";
import { useExport } from "@/lib/analysisExport";
import { addLog } from "@/lib/logStore";
import { cn, formatNumber } from "@/lib/utils";
import type { CorrelationResult } from "@/lib/analysisTypes";

type CorrState = {
  method: string;
  filter: string;
  result: CorrelationResult | null;
  error: string;
};

const DEFAULTS: CorrState = { method: "pearson", filter: "", result: null, error: "" };
const SCATTER_DEFAULTS = {
  x: "",
  y: "",
  groupBy: "",
  result: null,
  error: "",
} as Record<string, unknown>;

function cellTone(r: number | null): string {
  if (r == null) return "text-secondary";
  const a = Math.abs(r);
  if (a >= 0.9) return "bg-primary/45 text-text";
  if (a >= 0.7) return "bg-primary/30 text-text";
  if (a >= 0.4) return "bg-primary/15 text-text";
  return "text-secondary";
}

export function CorrelationPage() {
  const { t } = useI18n();
  const session = useSession();
  const { capabilities } = session;
  const call = useAnalysisCall();
  const navigate = useNavigate();
  const { exportKind, exportReport } = useExport("correlation");
  const [state, setState] = session.moduleState<CorrState>("correlation", DEFAULTS);
  const [, setScatter] = session.moduleState("scatter", SCATTER_DEFAULTS);
  const [busy, setBusy] = useState(false);

  const result = state.result;

  async function analyze() {
    setBusy(true);
    setState({ error: "" });
    try {
      const res = await call<CorrelationResult>("session_correlation", { method: state.method });
      setState({ result: res });
      addLog("OK", `Correlation (${res.method}) over ${res.columns.length} numeric column(s).`, "correlation");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setState({ error: msg, result: null });
      addLog("ERROR", msg, "correlation");
    } finally {
      setBusy(false);
    }
  }

  const columns = useMemo(() => {
    if (!result) return [];
    const q = state.filter.trim().toLowerCase();
    return q ? result.columns.filter((c) => c.toLowerCase().includes(q)) : result.columns;
  }, [result, state.filter]);

  function openScatter(x: string, y: string) {
    setScatter({ x, y, result: null, error: "" });
    navigate("/analysis/scatter");
  }

  return (
    <div>
      <PageHeader
        title={t("navCorrelation")}
        subtitle="Linear association between usable numeric columns. Correlation is not causation."
      />
      <DatasetBar />
      <AnalysisGate
        ready={capabilities.canCorrelation}
        requirement="Correlation requires at least two usable numeric columns. Unnamed, empty, identifier and binary artifact columns are excluded."
      >
        <div className="space-y-4">
          <SectionCard
            title="Method"
            actions={
              <ExportBar
                disabled={!result}
                items={[
                  { label: t("exportData"), onClick: () => exportKind("correlation", "correlation.xlsx") },
                  { label: t("exportReport"), onClick: () => exportReport("xlsx") },
                ]}
              />
            }
          >
            <div className="flex flex-wrap items-end gap-3">
              <Field
                label="Correlation method"
                className="w-48"
                info="Pearson measures a straight-line relationship. Spearman measures a consistent rank order and is less affected by outliers. Neither one proves that one column causes the other."
              >
                <Select
                  value={state.method}
                  onChange={(v) => setState({ method: v })}
                  options={[
                    { value: "pearson", label: "Pearson (linear)" },
                    { value: "spearman", label: "Spearman (rank)" },
                  ]}
                />
              </Field>
              <Field
                label="Search column"
                className="w-56"
                info="Hides matrix rows and columns whose name does not contain this text. The coefficients themselves are not recalculated."
              >
                <input
                  className="h-9 w-full rounded-lg border border-border bg-bg px-2 text-[12px] text-text"
                  placeholder="Filter matrix…"
                  value={state.filter}
                  onChange={(e) => setState({ filter: e.target.value })}
                />
              </Field>
              <Button onClick={analyze} disabled={busy}>
                <Play className="h-4 w-4 fill-current" />
                {busy ? t("analyzing") : "Calculate"}
              </Button>
            </div>
            {state.error ? <p className="mt-2 text-[12px] text-error">{state.error}</p> : null}
          </SectionCard>

          {!result ? (
            <Card>
              <CardBody className="py-16 text-center text-[13px] text-secondary">
                Run the calculation to build the correlation matrix.
              </CardBody>
            </Card>
          ) : result.columns.length < 2 ? (
            <Card>
              <CardBody className="py-12 text-center text-[13px] text-secondary">
                {result.message || "Not enough usable numeric columns."}
              </CardBody>
            </Card>
          ) : (
            <>
              <SectionCard
                title={`Correlation matrix (${result.method})`}
                subtitle="Click any cell to open the scatter plot for that pair."
                bodyClassName="overflow-auto"
              >
                <table className="text-left text-[11px]">
                  <thead className="text-secondary">
                    <tr>
                      <th className="sticky left-0 bg-card py-2 pr-2" />
                      {columns.map((c) => (
                        <th key={c} className="max-w-[80px] truncate px-1 font-medium" title={c}>
                          {c}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {columns.map((row) => (
                      <tr key={row} className="border-t border-border/40">
                        <td
                          className="sticky left-0 max-w-[180px] truncate bg-card py-1 pr-2 font-medium text-text"
                          title={row}
                        >
                          {row}
                        </td>
                        {columns.map((col) => {
                          const i = result.columns.indexOf(row);
                          const j = result.columns.indexOf(col);
                          const v = result.matrix[i]?.[j] ?? null;
                          return (
                            <td key={col} className="px-0.5 py-0.5">
                              <button
                                type="button"
                                disabled={row === col || v == null}
                                onClick={() => openScatter(row, col)}
                                className={cn(
                                  "w-full rounded px-1.5 py-1 text-right tabular-nums transition hover:ring-1 hover:ring-primary disabled:hover:ring-0",
                                  cellTone(v),
                                )}
                                title={`${row} vs ${col}`}
                              >
                                {v == null ? "—" : v.toFixed(2)}
                              </button>
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </SectionCard>

              <div className="grid gap-4 xl:grid-cols-2">
                <SectionCard
                  title="Strongest pairs"
                  subtitle="Sorted by absolute correlation"
                  bodyClassName="max-h-80 overflow-auto"
                >
                  <table className="w-full text-left text-[11.5px]">
                    <thead className="sticky top-0 bg-card text-secondary">
                      <tr>
                        <th className="py-2">X</th>
                        <th>Y</th>
                        <th className="text-right">r</th>
                        <th className="text-right">n</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {result.pairs.map((p) => (
                        <tr key={`${p.x}|${p.y}`} className="border-t border-border/50">
                          <td className="max-w-[150px] truncate py-1.5 text-text">{p.x}</td>
                          <td className="max-w-[150px] truncate">{p.y}</td>
                          <td className="text-right tabular-nums">{formatNumber(p.r, 3)}</td>
                          <td className="text-right tabular-nums">{p.n.toLocaleString()}</td>
                          <td className="text-right">
                            <Button size="sm" variant="ghost" onClick={() => openScatter(p.x, p.y)}>
                              Scatter
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </SectionCard>

                <SectionCard title={t("insights")}>
                  <InsightList insights={result.insights} />
                  {result.excluded.length ? (
                    <div className="mt-3 max-h-40 overflow-auto text-[11.5px] text-secondary">
                      <div className="mb-1 text-text">Excluded from the matrix:</div>
                      {result.excluded.map((c) => (
                        <div key={c.name} className="truncate">
                          {c.name} — {c.reason}
                        </div>
                      ))}
                    </div>
                  ) : null}
                </SectionCard>
              </div>
            </>
          )}
        </div>
      </AnalysisGate>
    </div>
  );
}
