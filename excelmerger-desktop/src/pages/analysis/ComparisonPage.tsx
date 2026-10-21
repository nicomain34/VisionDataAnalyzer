import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ErrorBar,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Play } from "lucide-react";
import { PageHeader } from "@/components/ui/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { DatasetBar, AnalysisGate } from "@/components/analysis/DatasetBar";
import { MiniBox } from "@/components/analysis/BoxPlotView";
import { PresetBar } from "@/components/analysis/PresetBar";
import {
  Checkbox,
  ExportBar,
  Field,
  InsightList,
  MetricGrid,
  SectionCard,
  Select,
  ValidationNote,
} from "@/components/analysis/Controls";
import { useI18n } from "@/lib/i18n";
import { useAnalysisCall, useSession } from "@/lib/analysisSession";
import { useExport } from "@/lib/analysisExport";
import { addLog } from "@/lib/logStore";
import { formatNumber } from "@/lib/utils";
import type { ComparisonResult } from "@/lib/analysisTypes";

type CompState = {
  column: string;
  groupBy: string;
  allowNumeric: boolean;
  buckets: number;
  topN: number;
  sortBy: string;
  filter: string;
  chart: "bar" | "box";
  result: ComparisonResult | null;
  error: string;
};

const DEFAULTS: CompState = {
  column: "",
  groupBy: "",
  allowNumeric: false,
  buckets: 8,
  topN: 20,
  sortBy: "count",
  filter: "",
  chart: "bar",
  result: null,
  error: "",
};

const FILE_GROUP = "__file";

export function ComparisonPage() {
  const { t } = useI18n();
  const session = useSession();
  const { profile, capabilities } = session;
  const call = useAnalysisCall();
  const { exportKind, exportReport } = useExport("comparison");
  const [state, setState] = session.moduleState<CompState>("comparison", DEFAULTS);
  const [busy, setBusy] = useState(false);

  const measurements = capabilities.measurements;
  const column = state.column && measurements.includes(state.column) ? state.column : measurements[0] || "";

  // Group By priority: categorical/boolean, then low-cardinality text, then file/batch.
  // Numeric measurements are offered only through the explicit advanced option and
  // are always compared as value ranges, never as one group per unique value.
  const groupOptions = useMemo(() => {
    const cols = profile?.columns ?? [];
    const suitable = cols.filter((c) => c.grouping_suitable && c.name !== column);
    const ordered = [...suitable].sort((a, b) => {
      const rank = (t: string) => (t === "categorical" ? 0 : t === "boolean" ? 1 : 2);
      const d = rank(String(a.col_type)) - rank(String(b.col_type));
      if (d !== 0) return d;
      return (a.cardinality ?? 0) - (b.cardinality ?? 0);
    });
    const options = ordered.map((c) => ({
      value: c.name,
      label: `${c.name} (${c.col_type}, ${c.cardinality ?? 0} values)`,
    }));
    options.push({ value: FILE_GROUP, label: t("groupByFile") });
    if (state.allowNumeric) {
      for (const c of cols) {
        if (c.col_type === "numeric" && c.usable_for_analysis && c.name !== column) {
          options.push({ value: c.name, label: `${c.name} (numeric → ${state.buckets} ranges)` });
        }
      }
    }
    return options;
  }, [profile, column, state.allowNumeric, state.buckets, t]);

  const groupBy =
    state.groupBy && groupOptions.some((o) => o.value === state.groupBy)
      ? state.groupBy
      : groupOptions[0]?.value || "";

  const hasGrouping = groupOptions.length > 0;
  const result = state.result;

  async function analyze() {
    if (!column || !groupBy) return;
    setBusy(true);
    setState({ error: "" });
    try {
      const res = await call<ComparisonResult>("session_comparison", {
        column,
        group_by: groupBy,
        allow_numeric_group: state.allowNumeric,
        numeric_buckets: state.buckets,
        top_n: state.topN,
        sort_by: state.sortBy,
      });
      setState({ result: res, column, groupBy });
      addLog(
        "OK",
        `Comparison ${res.value_col} by ${res.group_by}: ${res.total_groups} group(s).`,
        "comparison",
      );
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setState({ error: msg, result: null });
      addLog("ERROR", msg, "comparison");
    } finally {
      setBusy(false);
    }
  }

  const visibleGroups = useMemo(() => {
    if (!result) return [];
    const q = state.filter.trim().toLowerCase();
    return result.groups.filter((g) => !q || g.group.toLowerCase().includes(q));
  }, [result, state.filter]);

  const chartData = useMemo(
    () =>
      visibleGroups.slice(0, 24).map((g) => ({
        name: g.group.length > 16 ? `${g.group.slice(0, 15)}…` : g.group,
        full: g.group,
        mean: g.mean ?? 0,
        median: g.median ?? 0,
        err: [g.std ?? 0, g.std ?? 0] as [number, number],
      })),
    [visibleGroups],
  );

  const domain = useMemo(() => {
    const mins = visibleGroups.map((g) => g.min ?? 0);
    const maxs = visibleGroups.map((g) => g.max ?? 0);
    return { min: Math.min(...mins, 0), max: Math.max(...maxs, 1) };
  }, [visibleGroups]);

  return (
    <div>
      <PageHeader title={t("compareTitle")} subtitle={t("compareSubtitle")} />
      <DatasetBar />
      <AnalysisGate
        ready={capabilities.canDistribution}
        requirement="Comparison requires at least one usable numeric measurement column."
      >
        <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
          <div className="space-y-3">
            <SectionCard title="Analysis column" subtitle="Numeric measurement to compare">
              <Select
                value={column}
                onChange={(v) => setState({ column: v })}
                options={measurements.map((m) => ({ value: m, label: m }))}
              />
            </SectionCard>

            <SectionCard title={t("groupBy")} subtitle={t("compareHint")}>
              <div className="space-y-3">
                {!hasGrouping ? (
                  <ValidationNote>{t("noGroupColumns")}</ValidationNote>
                ) : (
                  <Field
                    label={t("groupBy")}
                    info="Split the measurement by a category, a batch, or the file name. Numeric measurements are not listed here, because each unique number would become its own group."
                  >
                    <Select
                      value={groupBy}
                      onChange={(v) => setState({ groupBy: v })}
                      options={groupOptions}
                    />
                  </Field>
                )}
                <Checkbox
                  checked={state.allowNumeric}
                  onChange={(v) => setState({ allowNumeric: v })}
                  label={t("allowNumericGroup")}
                  info="Use only when you intentionally want to compare ranges of a numeric column. Values are bucketed; they are never one group per unique number."
                />
                {state.allowNumeric ? (
                  <Field
                    label={`Numeric ranges: ${state.buckets}`}
                    hint="Numeric columns are bucketed into ranges instead of one group per value."
                    info="How many ranges the numeric grouping column is split into. More ranges show finer differences and need more data in each range."
                  >
                    <input
                      type="range"
                      className="em-range w-full"
                      min={2}
                      max={20}
                      value={state.buckets}
                      onChange={(e) => setState({ buckets: Number(e.target.value) })}
                    />
                  </Field>
                ) : null}
                <div className="grid grid-cols-2 gap-2">
                  <Field
                    label="Top groups"
                    info="Limits how many groups are drawn and listed. Useful when a category has dozens of values."
                  >
                    <Select
                      value={String(state.topN)}
                      onChange={(v) => setState({ topN: Number(v) })}
                      options={[10, 20, 30, 60].map((n) => ({ value: String(n), label: String(n) }))}
                    />
                  </Field>
                  <Field
                    label="Sort by"
                    info="Orders the groups. Count shows the largest samples first. Mean, standard deviation and outliers highlight process differences."
                  >
                    <Select
                      value={state.sortBy}
                      onChange={(v) => setState({ sortBy: v })}
                      options={[
                        { value: "count", label: "Count" },
                        { value: "mean", label: "Mean" },
                        { value: "std", label: "Std dev" },
                        { value: "outlier_count", label: "Outliers" },
                        { value: "group", label: "Name" },
                      ]}
                    />
                  </Field>
                </div>
                <Button
                  className="w-full"
                  onClick={analyze}
                  disabled={busy || !column || !groupBy || !hasGrouping}
                >
                  <Play className="h-4 w-4 fill-current" />
                  {busy ? t("analyzing") : t("analyzeCompare")}
                </Button>
                {state.error ? <p className="text-[12px] text-error">{state.error}</p> : null}
              </div>
            </SectionCard>

            <PresetBar
              type="comparison"
              config={{
                column,
                groupBy,
                allowNumeric: state.allowNumeric,
                buckets: state.buckets,
                topN: state.topN,
                sortBy: state.sortBy,
              }}
              requiredColumns={["column", "groupBy"]}
              onLoad={(cfg) => setState(cfg as Partial<CompState>)}
            />
          </div>

          <div className="min-w-0 space-y-4">
            {!result ? (
              <Card>
                <CardBody className="py-20 text-center text-[13px] text-secondary">
                  Choose a measurement and a grouping column, then run the comparison.
                </CardBody>
              </Card>
            ) : (
              <>
                <SectionCard
                  title={`${result.value_col} by ${result.group_by === FILE_GROUP ? "file" : result.group_by}`}
                  subtitle={`${result.total_groups} group(s)${result.truncated ? ` · showing top ${result.groups.length}` : ""}${
                    result.bucketed ? " · numeric column bucketed into ranges" : ""
                  }`}
                  actions={
                    <div className="flex items-center gap-2">
                      <Select
                        className="w-28"
                        value={state.chart}
                        onChange={(v) => setState({ chart: v as "bar" | "box" })}
                        options={[
                          { value: "bar", label: "Bar" },
                          { value: "box", label: "Box" },
                        ]}
                      />
                      <input
                        className="h-9 w-40 rounded-lg border border-border bg-bg px-2 text-[12px] text-text"
                        placeholder="Search groups…"
                        value={state.filter}
                        onChange={(e) => setState({ filter: e.target.value })}
                      />
                    </div>
                  }
                >
                  {state.chart === "bar" ? (
                    <div className="h-[300px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={chartData}>
                          <CartesianGrid stroke="#272D38" strokeDasharray="3 3" />
                          <XAxis
                            dataKey="name"
                            stroke="#8E98A8"
                            fontSize={10}
                            interval={0}
                            angle={-25}
                            textAnchor="end"
                            height={64}
                          />
                          <YAxis stroke="#8E98A8" fontSize={11} />
                          <Tooltip
                            contentStyle={{
                              background: "#191E28",
                              border: "1px solid #272D38",
                              borderRadius: 10,
                              fontSize: 12,
                            }}
                            labelFormatter={(label, payload) =>
                              String((payload?.[0]?.payload as { full?: string })?.full ?? label)
                            }
                          />
                          <Bar dataKey="mean" name="Mean" fill="#1683FF" radius={[3, 3, 0, 0]}>
                            <ErrorBar dataKey="err" stroke="#8E98A8" width={4} />
                          </Bar>
                          <Bar dataKey="median" name="Median" fill="#FFB020" radius={[3, 3, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <div className="max-h-[300px] space-y-1.5 overflow-auto">
                      {visibleGroups.slice(0, 40).map((g) => (
                        <div key={g.group} className="flex items-center gap-3">
                          <div className="w-40 truncate text-[11.5px] text-secondary">{g.group}</div>
                          <MiniBox stats={g} domain={domain} />
                          <div className="w-28 text-right text-[11px] tabular-nums text-secondary">
                            {formatNumber(g.median, 4)}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </SectionCard>

                <SectionCard
                  title="Comparison table"
                  actions={
                    <ExportBar
                      items={[
                        { label: t("exportData"), onClick: () => exportKind("comparison", "comparison.xlsx") },
                        { label: t("exportReport"), onClick: () => exportReport("xlsx") },
                      ]}
                    />
                  }
                  bodyClassName="max-h-[26rem] overflow-auto"
                >
                  <table className="w-full text-left text-[11.5px]">
                    <thead className="sticky top-0 bg-card text-secondary">
                      <tr>
                        <th className="py-2">Group</th>
                        <th className="text-right">Count</th>
                        <th className="text-right">Mean</th>
                        <th className="text-right">Median</th>
                        <th className="text-right">Std</th>
                        <th className="text-right">Min</th>
                        <th className="text-right">Max</th>
                        <th className="text-right">P5</th>
                        <th className="text-right">P95</th>
                        <th className="text-right">IQR</th>
                        <th className="text-right">Outliers</th>
                      </tr>
                    </thead>
                    <tbody>
                      {visibleGroups.map((g) => (
                        <tr key={g.group} className="border-t border-border/50">
                          <td className="max-w-[220px] truncate py-1.5 font-medium text-text">{g.group}</td>
                          <td className="text-right tabular-nums">{g.count.toLocaleString()}</td>
                          <td className="text-right tabular-nums">{formatNumber(g.mean, 4)}</td>
                          <td className="text-right tabular-nums">{formatNumber(g.median, 4)}</td>
                          <td className="text-right tabular-nums">{formatNumber(g.std, 4)}</td>
                          <td className="text-right tabular-nums">{formatNumber(g.min, 4)}</td>
                          <td className="text-right tabular-nums">{formatNumber(g.max, 4)}</td>
                          <td className="text-right tabular-nums">{formatNumber(g.p5, 4)}</td>
                          <td className="text-right tabular-nums">{formatNumber(g.p95, 4)}</td>
                          <td className="text-right tabular-nums">{formatNumber(g.iqr, 4)}</td>
                          <td className="text-right tabular-nums">{g.outlier_count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </SectionCard>

                {result.overall ? (
                  <SectionCard title="Overall (all groups combined)">
                    <MetricGrid
                      columns={6}
                      items={[
                        { label: "Count", value: result.overall.count.toLocaleString() },
                        { label: "Mean", value: formatNumber(result.overall.mean, 4) },
                        { label: "Median", value: formatNumber(result.overall.median, 4) },
                        { label: "Std", value: formatNumber(result.overall.std, 4) },
                        { label: "Min", value: formatNumber(result.overall.min, 4) },
                        { label: "Max", value: formatNumber(result.overall.max, 4) },
                      ]}
                    />
                  </SectionCard>
                ) : null}

                <SectionCard title={t("insights")}>
                  <InsightList insights={result.insights} />
                </SectionCard>
              </>
            )}
          </div>
        </div>
      </AnalysisGate>
    </div>
  );
}
