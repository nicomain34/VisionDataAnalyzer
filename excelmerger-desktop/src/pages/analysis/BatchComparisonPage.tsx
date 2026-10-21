import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
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
  ExportBar,
  Field,
  InsightList,
  NumberInput,
  SectionCard,
  Select,
} from "@/components/analysis/Controls";
import { useI18n } from "@/lib/i18n";
import { useAnalysisCall, useSession } from "@/lib/analysisSession";
import { useExport } from "@/lib/analysisExport";
import { addLog } from "@/lib/logStore";
import { formatNumber } from "@/lib/utils";
import type { BatchResult } from "@/lib/analysisTypes";

type BatchState = {
  column: string;
  unit: string;
  labelCol: string;
  lsl: string;
  usl: string;
  selected: string[];
  result: BatchResult | null;
  error: string;
};

const DEFAULTS: BatchState = {
  column: "",
  unit: "__file",
  labelCol: "",
  lsl: "",
  usl: "",
  selected: [],
  result: null,
  error: "",
};

export function BatchComparisonPage() {
  const { t } = useI18n();
  const session = useSession();
  const { profile, capabilities } = session;
  const call = useAnalysisCall();
  const { exportKind, exportReport } = useExport("batch");
  const [state, setState] = session.moduleState<BatchState>("batch", DEFAULTS);
  const [busy, setBusy] = useState(false);

  const measurements = capabilities.measurements;
  const column = state.column && measurements.includes(state.column) ? state.column : measurements[0] || "";
  const result = state.result;

  // Batch identifier candidates: the file itself, or any low-cardinality column.
  const unitOptions = useMemo(() => {
    const opts = [{ value: "__file", label: t("groupByFile") }];
    for (const c of profile?.columns ?? []) {
      if (c.grouping_suitable && c.name !== column) {
        opts.push({ value: c.name, label: `${c.name} (${c.cardinality ?? 0} values)` });
      }
    }
    return opts;
  }, [profile, column, t]);

  const unit = unitOptions.some((o) => o.value === state.unit) ? state.unit : "__file";

  async function analyze() {
    if (!column) return;
    setBusy(true);
    setState({ error: "" });
    try {
      const res = await call<BatchResult>("session_batch", {
        column,
        unit,
        label_col: state.labelCol || undefined,
        lsl: state.lsl.trim() === "" ? undefined : Number(state.lsl),
        usl: state.usl.trim() === "" ? undefined : Number(state.usl),
      });
      setState({ result: res, column, unit });
      addLog("OK", `Batch comparison ${column} by ${unit}: ${res.total_batches} unit(s).`, "batch");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setState({ error: msg, result: null });
      addLog("ERROR", msg, "batch");
    } finally {
      setBusy(false);
    }
  }

  const visible = useMemo(() => {
    if (!result) return [];
    if (!state.selected.length) return result.batches;
    return result.batches.filter((b) => state.selected.includes(b.batch));
  }, [result, state.selected]);

  const chartData = useMemo(
    () =>
      visible.slice(0, 24).map((b) => ({
        name: b.batch.length > 16 ? `${b.batch.slice(0, 15)}…` : b.batch,
        full: b.batch,
        mean: b.mean ?? 0,
        median: b.median ?? 0,
        pass: b.pass_rate ?? null,
      })),
    [visible],
  );

  const domain = useMemo(() => {
    const mins = visible.map((b) => b.min ?? 0);
    const maxs = visible.map((b) => b.max ?? 0);
    return { min: Math.min(...mins, 0), max: Math.max(...maxs, 1) };
  }, [visible]);

  function toggle(batch: string) {
    const next = state.selected.includes(batch)
      ? state.selected.filter((b) => b !== batch)
      : [...state.selected, batch];
    setState({ selected: next });
  }

  return (
    <div>
      <PageHeader
        title={t("navBatch")}
        subtitle="Compare files, batches or production periods — did the process get better or worse?"
      />
      <DatasetBar />
      <AnalysisGate
        ready={capabilities.canDistribution}
        requirement="Batch comparison requires at least one usable numeric measurement column."
      >
        <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
          <div className="space-y-3">
            <SectionCard title="Comparison setup">
              <div className="space-y-3">
                <Field
                  label="Measurement"
                  info="Numeric value compared across files, batches or another grouping column."
                >
                  <Select
                    value={column}
                    onChange={(v) => setState({ column: v })}
                    options={measurements.map((m) => ({ value: m, label: m }))}
                  />
                </Field>
                <Field
                  label="Batch unit"
                  hint="File name is used when no batch column exists"
                  info="What one bar represents: one file, or one value of a batch, station or shift column."
                >
                  <Select value={unit} onChange={(v) => setState({ unit: v })} options={unitOptions} />
                </Field>
                <Field
                  label="Pass/fail column"
                  hint="optional — enables pass rate"
                  info="Adds a pass-rate line when the column contains a recognized good/bad result such as OK/NG. Leave empty to compare the measurement only."
                >
                  <Select
                    value={state.labelCol}
                    onChange={(v) => setState({ labelCol: v })}
                    options={[
                      { value: "", label: "No label column" },
                      ...capabilities.labels.map((l) => ({ value: l, label: l })),
                    ]}
                  />
                </Field>
                <div className="grid grid-cols-2 gap-2">
                  <Field
                    label="LSL"
                    hint="optional"
                    info="Lower specification limit. Each batch then shows the share of values inside the limits."
                  >
                    <NumberInput value={state.lsl} onChange={(v) => setState({ lsl: v })} step="any" />
                  </Field>
                  <Field
                    label="USL"
                    hint="optional"
                    info="Upper specification limit. Used together with LSL, or alone, to compute the in-spec share."
                  >
                    <NumberInput value={state.usl} onChange={(v) => setState({ usl: v })} step="any" />
                  </Field>
                </div>
                <Button className="w-full" onClick={analyze} disabled={busy || !column}>
                  <Play className="h-4 w-4 fill-current" />
                  {busy ? t("analyzing") : "Compare"}
                </Button>
                {state.error ? <p className="text-[12px] text-error">{state.error}</p> : null}
              </div>
            </SectionCard>

            {result ? (
              <SectionCard
                title="Select units"
                subtitle={
                  state.selected.length
                    ? `${state.selected.length} selected (A/B comparison)`
                    : "All units shown"
                }
                bodyClassName="max-h-64 overflow-auto"
              >
                <div className="space-y-1">
                  {result.batches.map((b) => (
                    <label
                      key={b.batch}
                      className="flex items-center gap-2 text-[11.5px] text-secondary"
                    >
                      <input
                        type="checkbox"
                        className="em-check"
                        checked={state.selected.includes(b.batch)}
                        onChange={() => toggle(b.batch)}
                      />
                      <span className="truncate">{b.batch}</span>
                    </label>
                  ))}
                  {state.selected.length ? (
                    <Button size="sm" variant="ghost" onClick={() => setState({ selected: [] })}>
                      Clear selection
                    </Button>
                  ) : null}
                </div>
              </SectionCard>
            ) : null}

            <PresetBar
              type="batch"
              config={{ column, unit, labelCol: state.labelCol, lsl: state.lsl, usl: state.usl }}
              requiredColumns={["column"]}
              onLoad={(cfg) => setState(cfg as Partial<BatchState>)}
            />
          </div>

          <div className="min-w-0 space-y-4">
            {!result ? (
              <Card>
                <CardBody className="py-20 text-center text-[13px] text-secondary">
                  Pick a measurement and a batch unit, then run the comparison.
                </CardBody>
              </Card>
            ) : (
              <>
                <SectionCard
                  title={`${result.value_col} by ${result.unit === "__file" ? "file" : result.unit}`}
                  subtitle={`${result.total_batches} unit(s)${result.truncated ? " · truncated" : ""}`}
                  actions={
                    <ExportBar
                      items={[
                        { label: t("exportData"), onClick: () => exportKind("batch", "batch-comparison.xlsx") },
                        { label: t("exportReport"), onClick: () => exportReport("xlsx") },
                      ]}
                    />
                  }
                >
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
                        <YAxis yAxisId="left" stroke="#8E98A8" fontSize={11} />
                        {result.label_col ? (
                          <YAxis
                            yAxisId="right"
                            orientation="right"
                            stroke="#35C759"
                            fontSize={11}
                            domain={[0, 100]}
                          />
                        ) : null}
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
                        <Legend wrapperStyle={{ fontSize: 11 }} />
                        <Bar yAxisId="left" dataKey="mean" name="Mean" fill="#1683FF" radius={[3, 3, 0, 0]} />
                        <Bar
                          yAxisId="left"
                          dataKey="median"
                          name="Median"
                          fill="#FFB020"
                          radius={[3, 3, 0, 0]}
                        />
                        {result.label_col ? (
                          <Line
                            yAxisId="right"
                            dataKey="pass"
                            name="Pass rate %"
                            stroke="#35C759"
                            strokeWidth={2}
                            dot={{ r: 2 }}
                            isAnimationActive={false}
                          />
                        ) : null}
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </SectionCard>

                <SectionCard title="Batch table" bodyClassName="max-h-[26rem] overflow-auto">
                  <table className="w-full text-left text-[11.5px]">
                    <thead className="sticky top-0 bg-card text-secondary">
                      <tr>
                        <th className="py-2">Batch</th>
                        <th className="min-w-[130px]">Spread</th>
                        <th className="text-right">Count</th>
                        <th className="text-right">Mean</th>
                        <th className="text-right">Median</th>
                        <th className="text-right">Std</th>
                        <th className="text-right">Min</th>
                        <th className="text-right">Max</th>
                        <th className="text-right">P5</th>
                        <th className="text-right">P95</th>
                        <th className="text-right">Outliers</th>
                        {result.label_col ? <th className="text-right">Pass rate</th> : null}
                        {state.lsl || state.usl ? <th className="text-right">In spec</th> : null}
                      </tr>
                    </thead>
                    <tbody>
                      {visible.map((b) => (
                        <tr key={b.batch} className="border-t border-border/50">
                          <td className="max-w-[200px] truncate py-1.5 font-medium text-text">{b.batch}</td>
                          <td>
                            <MiniBox stats={b} domain={domain} />
                          </td>
                          <td className="text-right tabular-nums">{b.count.toLocaleString()}</td>
                          <td className="text-right tabular-nums">{formatNumber(b.mean, 4)}</td>
                          <td className="text-right tabular-nums">{formatNumber(b.median, 4)}</td>
                          <td className="text-right tabular-nums">{formatNumber(b.std, 4)}</td>
                          <td className="text-right tabular-nums">{formatNumber(b.min, 4)}</td>
                          <td className="text-right tabular-nums">{formatNumber(b.max, 4)}</td>
                          <td className="text-right tabular-nums">{formatNumber(b.p5, 4)}</td>
                          <td className="text-right tabular-nums">{formatNumber(b.p95, 4)}</td>
                          <td className="text-right tabular-nums">{b.outlier_count}</td>
                          {result.label_col ? (
                            <td className="text-right tabular-nums text-success">
                              {b.pass_rate == null ? "—" : `${formatNumber(b.pass_rate, 3)}%`}
                            </td>
                          ) : null}
                          {state.lsl || state.usl ? (
                            <td className="text-right tabular-nums">
                              {b.in_spec_pct == null ? "—" : `${formatNumber(b.in_spec_pct, 3)}%`}
                            </td>
                          ) : null}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </SectionCard>

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
