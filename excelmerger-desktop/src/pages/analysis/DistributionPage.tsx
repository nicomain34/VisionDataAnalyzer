import { useMemo, useState } from "react";
import {
  Area,
  Bar,
  CartesianGrid,
  ComposedChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Play } from "lucide-react";
import { PageHeader } from "@/components/ui/PageHeader";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Card, CardBody } from "@/components/ui/Card";
import { DatasetBar, AnalysisGate } from "@/components/analysis/DatasetBar";
import { BoxPlotView } from "@/components/analysis/BoxPlotView";
import {
  Checkbox,
  ExportBar,
  Field,
  InsightList,
  MetricGrid,
  NumberInput,
  SectionCard,
  Select,
  statsItems,
} from "@/components/analysis/Controls";
import { useI18n } from "@/lib/i18n";
import { useAnalysisCall, useSession } from "@/lib/analysisSession";
import { useExport } from "@/lib/analysisExport";
import { addLog } from "@/lib/logStore";
import { cn, formatNumber } from "@/lib/utils";
import { PresetBar } from "@/components/analysis/PresetBar";
import type { DistributionResult } from "@/lib/analysisTypes";

type ChartShow = "histogram" | "kde" | "box";
type RightTab = "distribution" | "statistics" | "insights" | "outliers";

type DistState = {
  column: string;
  bins: number;
  logY: boolean;
  chartShow: ChartShow;
  lsl: string;
  usl: string;
  outliersOnly: boolean;
  tab: RightTab;
  result: DistributionResult | null;
  error: string;
};

const DEFAULTS: DistState = {
  column: "",
  bins: 50,
  logY: false,
  chartShow: "histogram",
  lsl: "",
  usl: "",
  outliersOnly: false,
  tab: "distribution",
  result: null,
  error: "",
};

function nearestBin(value: number | null, edges: number[], keys: string[]): string | undefined {
  if (value == null || !edges.length || !keys.length) return undefined;
  let best = 0;
  let dist = Infinity;
  for (let i = 0; i < keys.length; i++) {
    const mid = (edges[i] + edges[i + 1]) / 2;
    const d = Math.abs(mid - value);
    if (d < dist) {
      dist = d;
      best = i;
    }
  }
  return keys[best];
}

export function DistributionPage({ forceMode }: { forceMode?: "outliers" }) {
  const { t } = useI18n();
  const session = useSession();
  const { profile, capabilities } = session;
  const call = useAnalysisCall();
  const { exportKind, exportReport } = useExport("distribution");
  const [state, setState] = session.moduleState<DistState>("distribution", DEFAULTS);
  const [busy, setBusy] = useState(false);

  const measurements = capabilities.measurements;
  const column = state.column && measurements.includes(state.column) ? state.column : measurements[0] || "";
  const result = state.result;
  const activeTab: RightTab = forceMode === "outliers" && state.tab === "distribution" ? "outliers" : state.tab;

  async function analyze() {
    if (!column) return;
    setBusy(true);
    setState({ error: "" });
    try {
      const res = await call<DistributionResult>("session_distribution", {
        column,
        bins: state.bins,
        lsl: state.lsl.trim() === "" ? undefined : Number(state.lsl),
        usl: state.usl.trim() === "" ? undefined : Number(state.usl),
        outliers_only: false,
      });
      setState({
        result: res,
        column,
        tab: forceMode === "outliers" ? "outliers" : "distribution",
      });
      addLog(
        "OK",
        `Distribution ${res.column}: ${res.stats.count.toLocaleString()} values, ${res.outlier_count} outliers.`,
        "distribution",
      );
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setState({ error: msg, result: null });
      addLog("ERROR", msg, "distribution");
    } finally {
      setBusy(false);
    }
  }

  const chartData = useMemo(() => {
    if (!result?.hist_counts?.length) return [];
    return result.hist_counts.map((count, i) => {
      const lo = result.hist_edges[i];
      const hi = result.hist_edges[i + 1];
      return {
        bin: ((lo + hi) / 2).toPrecision(4),
        count: state.logY ? Math.log10(Math.max(count, 1)) : count,
        raw: count,
      };
    });
  }, [result, state.logY]);

  const kdeData = useMemo(
    () => (result?.kde || []).map((p) => ({ x: p.x.toPrecision(4), d: p.d })),
    [result],
  );

  const binKeys = chartData.map((d) => d.bin);
  const tabs: { id: RightTab; label: string }[] = [
    { id: "distribution", label: t("tabDistribution") },
    { id: "statistics", label: t("statistics") },
    { id: "insights", label: t("insights") },
    {
      id: "outliers",
      label: result ? t("tabOutliersCount", { count: result.outlier_count }) : t("outliers"),
    },
  ];

  const colMeta = profile?.columns.find((c) => c.name === column);

  return (
    <div>
      <PageHeader
        title={forceMode === "outliers" ? t("outliersTitle") : t("distTitle")}
        subtitle={forceMode === "outliers" ? t("outliersSubtitle") : t("distSubtitle")}
      />
      <DatasetBar />
      <AnalysisGate
        ready={capabilities.canDistribution}
        requirement="Distribution requires at least one usable numeric measurement column. None was detected in this dataset."
      >
        <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
          <div className="space-y-3">
            <SectionCard title={t("selectColumn")}>
              <div className="space-y-2">
                <Select
                  value={column}
                  onChange={(v) => setState({ column: v })}
                  options={measurements.map((m) => ({ value: m, label: m }))}
                />
                {colMeta ? (
                  <div className="flex flex-wrap items-center gap-2 text-[11.5px] text-secondary">
                    <Badge tone="primary">{String(colMeta.col_type)}</Badge>
                    <span>
                      {(colMeta.count ?? 0).toLocaleString()} values ·{" "}
                      {colMeta.file_count < (profile?.files_scanned ?? 0)
                        ? `in ${colMeta.file_count} of ${profile?.files_scanned} files`
                        : "in all files"}
                    </span>
                  </div>
                ) : null}
              </div>
            </SectionCard>

            <SectionCard title={t("analysisOptions")}>
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-2">
                  <Field
                    label={t("chartType")}
                    info="Histogram shows how many values fall in each bin. KDE is a smooth density. Box plot summarizes min, quartiles and max."
                  >
                    <Select
                      value={state.chartShow}
                      onChange={(v) => setState({ chartShow: v as ChartShow })}
                      options={[
                        { value: "histogram", label: "Histogram" },
                        { value: "kde", label: "KDE" },
                        { value: "box", label: "Box Plot" },
                      ]}
                    />
                  </Field>
                  <Field
                    label={`${t("bins")}: ${state.bins}`}
                    info="Number of histogram bars. Fewer bars show the overall shape. More bars show local gaps, if the sample is large enough."
                  >
                    <input
                      type="range"
                      className="em-range mt-2 w-full"
                      min={10}
                      max={120}
                      value={state.bins}
                      onChange={(e) => setState({ bins: Number(e.target.value) })}
                    />
                  </Field>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <Field
                    label="LSL"
                    hint="optional"
                    info="Lower specification limit. When set, the page reports how many values fall below it."
                  >
                    <NumberInput value={state.lsl} onChange={(v) => setState({ lsl: v })} step="any" />
                  </Field>
                  <Field
                    label="USL"
                    hint="optional"
                    info="Upper specification limit. When set, the page reports how many values fall above it."
                  >
                    <NumberInput value={state.usl} onChange={(v) => setState({ usl: v })} step="any" />
                  </Field>
                </div>
                <Checkbox
                  checked={state.logY}
                  onChange={(v) => setState({ logY: v })}
                  label={t("logScale")}
                  info="Use when a few very large values flatten the rest of the histogram. Statistics stay on the original scale."
                />
                <Checkbox
                  checked={state.outliersOnly}
                  onChange={(v) => setState({ outliersOnly: v })}
                  label={t("outliersOnly")}
                  info="Shows only rows outside 1.5 × IQR. Statistics are still calculated on the full valid sample."
                />
                <Button className="w-full" onClick={analyze} disabled={busy || !column}>
                  <Play className="h-4 w-4 fill-current" />
                  {busy ? t("analyzing") : t("analyze")}
                </Button>
                {state.error ? (
                  <p className="text-[12px] text-error">{state.error}</p>
                ) : null}
              </div>
            </SectionCard>

            <PresetBar
              type="distribution"
              config={{
                column,
                bins: state.bins,
                chartShow: state.chartShow,
                lsl: state.lsl,
                usl: state.usl,
                logY: state.logY,
                outliersOnly: state.outliersOnly,
              }}
              requiredColumns={[column]}
              onLoad={(cfg) => setState(cfg as Partial<DistState>)}
            />
          </div>

          <div className="min-w-0">
            {!result ? (
              <Card>
                <CardBody className="py-20 text-center text-[13px] text-secondary">
                  Select a measurement column and run the analysis.
                </CardBody>
              </Card>
            ) : (
              <div className="space-y-4">
                <div className="flex gap-1 border-b border-border">
                  {tabs.map((tab) => (
                    <button
                      key={tab.id}
                      type="button"
                      onClick={() => setState({ tab: tab.id })}
                      className={cn(
                        "relative px-4 py-2.5 text-[13px] font-medium transition",
                        activeTab === tab.id ? "text-primary" : "text-secondary hover:text-text",
                      )}
                    >
                      {tab.label}
                      {activeTab === tab.id ? (
                        <span className="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-primary" />
                      ) : null}
                    </button>
                  ))}
                </div>

                {activeTab === "distribution" ? (
                  <SectionCard
                    title={t("distributionOf", { column: result.column })}
                    subtitle={`${result.stats.count.toLocaleString()} values from ${result.files_with_column} file(s)${
                      result.excluded_values ? ` · ${result.excluded_values} invalid excluded` : ""
                    }`}
                  >
                    <div className="h-[300px]">
                      {state.chartShow === "box" ? (
                        <BoxPlotView stats={result.stats} />
                      ) : (
                        <ResponsiveContainer width="100%" height="100%">
                          <ComposedChart
                            data={
                              (state.chartShow === "kde"
                                ? kdeData
                                : chartData) as unknown as typeof chartData
                            }
                          >
                            <CartesianGrid stroke="#272D38" strokeDasharray="3 3" />
                            <XAxis
                              dataKey={state.chartShow === "kde" ? "x" : "bin"}
                              stroke="#8E98A8"
                              fontSize={10}
                              minTickGap={18}
                            />
                            <YAxis stroke="#8E98A8" fontSize={11} />
                            <Tooltip
                              contentStyle={{
                                background: "#191E28",
                                border: "1px solid #272D38",
                                borderRadius: 10,
                                fontSize: 12,
                              }}
                            />
                            {state.chartShow === "kde" ? (
                              <Area
                                dataKey="d"
                                name="density"
                                stroke="#1683FF"
                                fill="#1683FF"
                                fillOpacity={0.22}
                              />
                            ) : (
                              <Bar dataKey="count" name="count" fill="#1683FF" radius={[3, 3, 0, 0]} />
                            )}
                            {state.chartShow === "histogram" ? (
                              <>
                                <ReferenceLine
                                  x={nearestBin(result.stats.mean, result.hist_edges, binKeys)}
                                  stroke="#35C759"
                                  strokeDasharray="4 4"
                                  label={{ value: "mean", fill: "#35C759", fontSize: 10 }}
                                />
                                <ReferenceLine
                                  x={nearestBin(result.stats.median, result.hist_edges, binKeys)}
                                  stroke="#FFB020"
                                  strokeDasharray="4 4"
                                  label={{ value: "median", fill: "#FFB020", fontSize: 10 }}
                                />
                                {result.spec.enabled && result.spec.lsl != null ? (
                                  <ReferenceLine
                                    x={nearestBin(result.spec.lsl, result.hist_edges, binKeys)}
                                    stroke="#FF4D5F"
                                    label={{ value: "LSL", fill: "#FF4D5F", fontSize: 10 }}
                                  />
                                ) : null}
                                {result.spec.enabled && result.spec.usl != null ? (
                                  <ReferenceLine
                                    x={nearestBin(result.spec.usl, result.hist_edges, binKeys)}
                                    stroke="#FF4D5F"
                                    label={{ value: "USL", fill: "#FF4D5F", fontSize: 10 }}
                                  />
                                ) : null}
                              </>
                            ) : null}
                          </ComposedChart>
                        </ResponsiveContainer>
                      )}
                    </div>
                    {result.spec.enabled ? (
                      <div className="mt-3">
                        <MetricGrid
                          columns={6}
                          items={[
                            { label: "In spec", value: (result.spec.in_spec ?? 0).toLocaleString() },
                            { label: "Out of spec", value: (result.spec.out_spec ?? 0).toLocaleString() },
                            { label: "Below LSL", value: (result.spec.below_lsl ?? 0).toLocaleString() },
                            { label: "Above USL", value: (result.spec.above_usl ?? 0).toLocaleString() },
                            {
                              label: "Pass",
                              value: `${formatNumber(result.spec.pass_pct, 3)}%`,
                              tone: "success",
                            },
                            {
                              label: "Fail",
                              value: `${formatNumber(result.spec.fail_pct, 3)}%`,
                              tone: (result.spec.fail_pct ?? 0) > 0 ? "warning" : "default",
                            },
                          ]}
                        />
                      </div>
                    ) : null}
                  </SectionCard>
                ) : null}

                {activeTab === "statistics" ? (
                  <SectionCard
                    title={t("statistics")}
                    subtitle={
                      result.stats.excluded
                        ? `${result.stats.excluded} value(s) excluded as NaN/invalid/infinite`
                        : "All valid values were used"
                    }
                    actions={
                      <ExportBar
                        items={[
                          {
                            label: t("exportStats"),
                            onClick: () => exportKind("statistics", "statistics.xlsx"),
                          },
                        ]}
                      />
                    }
                  >
                    <MetricGrid columns={5} items={statsItems(result.stats as unknown as Record<string, number | null>)} />
                  </SectionCard>
                ) : null}

                {activeTab === "insights" ? (
                  <SectionCard title={t("insights")}>
                    <InsightList insights={result.insights} />
                  </SectionCard>
                ) : null}

                {activeTab === "outliers" ? (
                  <SectionCard
                    title={t("tabOutliersCount", { count: result.outlier_count })}
                    subtitle={t("iqrMethod")}
                    actions={
                      <ExportBar
                        items={[
                          { label: "Export outliers", onClick: () => exportKind("outliers", "outliers.xlsx") },
                        ]}
                      />
                    }
                  >
                    <MetricGrid
                      columns={4}
                      items={[
                        { label: "Outliers", value: result.outlier_count.toLocaleString() },
                        { label: "Share", value: `${formatNumber(result.outlier_pct, 3)}%` },
                        { label: "Lower bound", value: formatNumber(result.bounds.lower, 4) },
                        { label: "Upper bound", value: formatNumber(result.bounds.upper, 4) },
                      ]}
                    />
                    <p className="mt-3 text-[12px] text-secondary">{t("iqrExplain")}</p>
                  </SectionCard>
                ) : null}

                <SectionCard
                  title={t("preview")}
                  subtitle={`${result.preview.length} of ${result.stats.count.toLocaleString()} rows`}
                  actions={
                    <div className="flex flex-wrap items-center gap-2">
                      <Checkbox
                        checked={state.outliersOnly}
                        onChange={(v) => setState({ outliersOnly: v })}
                        label={t("outliersOnly")}
                  info="Shows only rows outside 1.5 × IQR. Statistics are still calculated on the full valid sample."
                      />
                      <ExportBar
                        items={[
                          { label: t("exportData"), onClick: () => exportKind("data", "distribution.xlsx") },
                          { label: t("exportReport"), onClick: () => exportReport("xlsx") },
                        ]}
                      />
                    </div>
                  }
                  bodyClassName="max-h-72 overflow-auto"
                >
                  <table className="w-full text-left text-[11.5px]">
                    <thead className="sticky top-0 bg-card text-secondary">
                      <tr>
                        <th className="py-2">#</th>
                        <th>{t("colFileName")}</th>
                        <th>{t("colSheetName")}</th>
                        <th className="text-right">{result.column}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.preview
                        .filter((r) => (state.outliersOnly ? Boolean(r.Outlier) : true))
                        .slice(0, 200)
                        .map((r) => (
                          <tr key={String(r["#"])} className="border-t border-border/50">
                            <td className="py-1.5">{String(r["#"])}</td>
                            <td className="max-w-[220px] truncate">{String(r["File name"])}</td>
                            <td>{String(r["Sheet name"])}</td>
                            <td
                              className={cn(
                                "text-right tabular-nums",
                                Boolean(r.Outlier) && "font-semibold text-error",
                              )}
                            >
                              {formatNumber(Number(r[result.column]), 5)}
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </SectionCard>
              </div>
            )}
          </div>
        </div>
      </AnalysisGate>
    </div>
  );
}
