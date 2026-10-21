import { useEffect, useMemo, useState } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
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
import { PresetBar } from "@/components/analysis/PresetBar";
import {
  ExportBar,
  Field,
  InsightList,
  MetricGrid,
  NumberInput,
  SectionCard,
  Select,
  ValidationNote,
} from "@/components/analysis/Controls";
import { useI18n } from "@/lib/i18n";
import { useAnalysisCall, useSession } from "@/lib/analysisSession";
import { useExport } from "@/lib/analysisExport";
import { addLog } from "@/lib/logStore";
import { formatNumber } from "@/lib/utils";
import type { LimitResult, ThresholdRow } from "@/lib/analysisTypes";

type LimitState = {
  measurement: string;
  labelCol: string;
  passValue: string;
  failValue: string;
  limitType: "upper" | "lower" | "two_sided";
  optimization: string;
  statMethod: string;
  costFA: string;
  costFR: string;
  currentLower: string;
  currentUpper: string;
  slider: number | null;
  result: LimitResult | null;
  error: string;
};

const DEFAULTS: LimitState = {
  measurement: "",
  labelCol: "",
  passValue: "",
  failValue: "",
  limitType: "upper",
  optimization: "youden",
  statMethod: "percentile",
  costFA: "10",
  costFR: "1",
  currentLower: "",
  currentUpper: "",
  slider: null,
  result: null,
  error: "",
};

function pct(v: number | null | undefined) {
  return v == null ? "—" : `${(v * 100).toFixed(2)}%`;
}

/** Nearest evaluated threshold row — the sweep is already on the client. */
function rowAt(rows: ThresholdRow[] | undefined, value: number | null): ThresholdRow | null {
  if (!rows?.length || value == null) return null;
  let best = rows[0];
  let dist = Infinity;
  for (const r of rows) {
    const d = Math.abs(r.threshold - value);
    if (d < dist) {
      dist = d;
      best = r;
    }
  }
  return best;
}

export function LimitFinderPage() {
  const { t } = useI18n();
  const session = useSession();
  const { capabilities } = session;
  const call = useAnalysisCall();
  const { exportKind, exportReport } = useExport("limit");
  const [state, setState] = session.moduleState<LimitState>("limit", DEFAULTS);
  const [busy, setBusy] = useState(false);
  const [labelValues, setLabelValues] = useState<{ value: string; count: number }[]>([]);
  const [labelDistinct, setLabelDistinct] = useState(0);

  const { profile } = session;
  const measurements = capabilities.measurements;
  const measurement =
    state.measurement && measurements.includes(state.measurement) ? state.measurement : measurements[0] || "";
  const columnNames = useMemo(() => (profile?.columns ?? []).map((c) => c.name), [profile]);
  const labelCol = state.labelCol && columnNames.includes(state.labelCol) ? state.labelCol : "";
  const passValue = state.passValue ?? "";
  const failValue = state.failValue ?? "";
  const result = state.result;
  const supervised = Boolean(result?.supervised);

  useEffect(() => {
    if (!labelCol) {
      setLabelValues([]);
      setLabelDistinct(0);
      return;
    }
    let cancelled = false;
    call<{ values: { value: string; count: number }[]; distinct: number }>("session_column_values", {
      column: labelCol,
    })
      .then((res) => {
        if (cancelled) return;
        setLabelValues(res.values || []);
        setLabelDistinct(res.distinct || 0);
      })
      .catch(() => {
        if (!cancelled) {
          setLabelValues([]);
          setLabelDistinct(0);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [call, labelCol]);

  function selectLabel(name: string) {
    const col = profile?.columns.find((c) => c.name === name);
    setState({
      labelCol: name,
      passValue: col?.labels_recognized ? col.positive_label || "" : "",
      failValue: col?.labels_recognized ? col.negative_label || "" : "",
      slider: null,
    });
  }

  useEffect(() => {
    if (!result?.supervised) return;
    if (state.slider != null) return;
    const rec = result.recommended?.threshold;
    if (rec != null) setState({ slider: rec });
  }, [result, state.slider, setState]);

  async function analyze() {
    if (!measurement) return;
    if (labelCol && (!passValue.trim() || !failValue.trim())) {
      setState({ error: "Choose which value is PASS and which is FAIL." });
      return;
    }
    setBusy(true);
    setState({ error: "" });
    try {
      const res = await call<LimitResult>("session_limit_finder", {
        measurement,
        label_col: labelCol || undefined,
        positive_label: labelCol ? passValue.trim() : undefined,
        negative_label: labelCol ? failValue.trim() : undefined,
        limit_type: state.limitType,
        optimization: state.optimization,
        stat_method: state.statMethod,
        cost_false_accept: Number(state.costFA) || 10,
        cost_false_reject: Number(state.costFR) || 1,
        current_lower: state.currentLower.trim() === "" ? undefined : Number(state.currentLower),
        current_upper: state.currentUpper.trim() === "" ? undefined : Number(state.currentUpper),
      });
      setState({
        result: res,
        measurement,
        labelCol,
        passValue,
        failValue,
        slider: res.recommended?.threshold ?? null,
      });
      addLog(
        "OK",
        `Limit Finder (${res.mode}) ${measurement}: ` +
          `${res.recommended_lower != null ? `lower ${formatNumber(res.recommended_lower, 4)} ` : ""}` +
          `${res.recommended_upper != null ? `upper ${formatNumber(res.recommended_upper, 4)}` : ""}`,
        "limit",
      );
      for (const w of res.warnings || []) addLog("WARN", w, "limit");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setState({ error: msg, result: null });
      addLog("ERROR", msg, "limit");
    } finally {
      setBusy(false);
    }
  }

  const sliderRow = useMemo(
    () => rowAt(result?.thresholds, state.slider),
    [result, state.slider],
  );

  const boundaryData = useMemo(() => {
    const b = result?.boundary;
    if (!b?.edges?.length) return [];
    return b.edges.slice(0, -1).map((edge, i) => ({
      x: Number(((edge + b.edges[i + 1]) / 2).toPrecision(4)),
      ok: b.ok[i] ?? 0,
      ng: b.ng[i] ?? 0,
    }));
  }, [result]);

  const thresholdChart = useMemo(
    () =>
      (result?.thresholds || []).map((r) => ({
        threshold: Number(r.threshold.toPrecision(5)),
        falseAccept: r.false_accept_rate * 100,
        falseReject: r.false_reject_rate * 100,
        yieldPct: r.yield * 100,
      })),
    [result],
  );

  const range = result?.value_range;
  const sliderMin = range?.min ?? 0;
  const sliderMax = range?.max ?? 1;
  const step = (sliderMax - sliderMin) / 200 || 0.01;

  return (
    <div>
      <PageHeader
        title={t("navLimit")}
        subtitle="Find a measurement threshold that separates good and defective production data."
      />
      <DatasetBar />
      <AnalysisGate
        ready={capabilities.canDistribution}
        requirement="Limit Finder requires at least one usable numeric measurement column."
      >
        <div className="grid gap-4 lg:grid-cols-[330px_1fr]">
          <div className="space-y-3">
            <SectionCard title="Inputs">
              <div className="space-y-3">
                <Field
                  label="Measurement"
                  info="Numeric value the limit is calculated on, for example a dimension or a sensor reading."
                >
                  <Select
                    value={measurement}
                    onChange={(v) => setState({ measurement: v, slider: null })}
                    options={measurements.map((m) => ({ value: m, label: m }))}
                  />
                </Field>
                <Field
                  label="Result / label column"
                  info="Any column that stores the inspection decision. The program does not assume the column name or that it contains only OK and NG."
                >
                  <Select
                    value={labelCol}
                    onChange={selectLabel}
                    options={[
                      { value: "", label: "None (statistical only)" },
                      ...columnNames.map((name) => ({ value: name, label: name })),
                    ]}
                  />
                </Field>
                {labelCol ? (
                  <>
                    <Field
                      label="PASS / OK value"
                      info="The cell value that means a good unit. Type it or pick it from the values found in the column, for example OK, PASS or 1."
                    >
                      <input
                        className="h-9 w-full rounded-lg border border-border bg-bg px-2 text-[12px] text-text"
                        list="limit-pass-values"
                        value={passValue}
                        placeholder="e.g. OK, PASS, 1"
                        onChange={(e) => setState({ passValue: e.target.value, slider: null })}
                      />
                      <datalist id="limit-pass-values">
                        {labelValues.map((v) => (
                          <option key={v.value} value={v.value} />
                        ))}
                      </datalist>
                    </Field>
                    <Field
                      label="FAIL / NG value"
                      info="The cell value that means a defective unit. Rows with any other value are excluded from the supervised limit."
                    >
                      <input
                        className="h-9 w-full rounded-lg border border-border bg-bg px-2 text-[12px] text-text"
                        list="limit-fail-values"
                        value={failValue}
                        placeholder="e.g. NG, FAIL, 0"
                        onChange={(e) => setState({ failValue: e.target.value, slider: null })}
                      />
                      <datalist id="limit-fail-values">
                        {labelValues.map((v) => (
                          <option key={v.value} value={v.value} />
                        ))}
                      </datalist>
                    </Field>
                    {labelDistinct > labelValues.length ? (
                      <p className="text-[10.5px] text-secondary">
                        Showing the {labelValues.length} most frequent values of {labelDistinct}. Type a value if it is
                        not listed.
                      </p>
                    ) : null}
                  </>
                ) : null}
                <Field
                  label="Limit type"
                  info="Upper rejects values above the limit. Lower rejects values below it. Two-sided rejects both tails."
                >
                  <Select
                    value={state.limitType}
                    onChange={(v) => setState({ limitType: v as LimitState["limitType"], slider: null })}
                    options={[
                      { value: "upper", label: "Upper (value > limit ⇒ fail)" },
                      { value: "lower", label: "Lower (value < limit ⇒ fail)" },
                      { value: "two_sided", label: "Two-sided" },
                    ]}
                  />
                </Field>
                {labelCol ? (
                  <>
                    <Field
                      label="Optimization"
                      info="Youden J balances missed defects and false rejects. Use cost when a missed defect is more expensive than rejecting a good unit. F1 and accuracy are alternatives."
                    >
                      <Select
                        value={state.optimization}
                        onChange={(v) => setState({ optimization: v })}
                        options={[
                          { value: "youden", label: "Youden J" },
                          { value: "f1", label: "F1 score" },
                          { value: "cost", label: "Minimum expected cost" },
                          { value: "accuracy", label: "Accuracy" },
                        ]}
                      />
                    </Field>
                    {state.optimization === "cost" ? (
                      <div className="grid grid-cols-2 gap-2">
                        <Field
                          label="False accept cost"
                          info="Relative cost of letting a defective unit pass. Higher values push the limit toward catching more defects."
                        >
                          <NumberInput value={state.costFA} onChange={(v) => setState({ costFA: v })} />
                        </Field>
                        <Field
                          label="False reject cost"
                          info="Relative cost of rejecting a good unit. Higher values keep more good units and may miss more defects."
                        >
                          <NumberInput value={state.costFR} onChange={(v) => setState({ costFR: v })} />
                        </Field>
                      </div>
                    ) : null}
                  </>
                ) : (
                  <Field
                    label="Statistical method"
                    info="Used only when no label column is selected. These limits describe the measurement distribution. They are not a validated defect boundary."
                  >
                    <Select
                      value={state.statMethod}
                      onChange={(v) => setState({ statMethod: v })}
                      options={[
                        { value: "percentile", label: "Percentile (0.135 / 99.865)" },
                        { value: "iqr", label: "IQR (1.5 × IQR)" },
                        { value: "sigma", label: "Mean ± 3σ" },
                        { value: "robust", label: "Robust (median ± 3 × MAD)" },
                      ]}
                    />
                  </Field>
                )}
                <div className="grid grid-cols-2 gap-2">
                  <Field
                    label="Current lower"
                    hint="optional"
                    info="The lower limit in use today, so the page can compare it with the recommended one."
                  >
                    <NumberInput
                      value={state.currentLower}
                      onChange={(v) => setState({ currentLower: v })}
                      step="any"
                    />
                  </Field>
                  <Field
                    label="Current upper"
                    hint="optional"
                    info="The upper limit in use today, so the page can compare it with the recommended one."
                  >
                    <NumberInput
                      value={state.currentUpper}
                      onChange={(v) => setState({ currentUpper: v })}
                      step="any"
                    />
                  </Field>
                </div>
                <Button className="w-full" onClick={analyze} disabled={busy || !measurement}>
                  <Play className="h-4 w-4 fill-current" />
                  {busy ? t("analyzing") : "Find limit"}
                </Button>
                {state.error ? <p className="text-[12px] text-error">{state.error}</p> : null}
              </div>
            </SectionCard>

            <PresetBar
              type="limit"
              config={{
                measurement,
                labelCol,
                passValue,
                failValue,
                limitType: state.limitType,
                optimization: state.optimization,
                statMethod: state.statMethod,
                costFA: state.costFA,
                costFR: state.costFR,
                currentLower: state.currentLower,
                currentUpper: state.currentUpper,
              }}
              requiredColumns={["measurement", "labelCol"]}
              onLoad={(cfg) => setState({ ...(cfg as Partial<LimitState>), slider: null })}
            />
          </div>

          <div className="min-w-0 space-y-4">
            {!result ? (
              <Card>
                <CardBody className="py-20 text-center text-[13px] text-secondary">
                  Select a measurement (and a pass/fail column for supervised optimization), then run
                  the limit search.
                </CardBody>
              </Card>
            ) : (
              <>
                <SectionCard
                  title="Recommended limit"
                  subtitle={result.optimization_method}
                  actions={
                    <div className="flex items-center gap-2">
                      <Badge tone={supervised ? "success" : "warning"}>
                        {supervised ? "Supervised (labelled data)" : "Statistical only"}
                      </Badge>
                      <ExportBar
                        items={[
                          {
                            label: "Thresholds",
                            onClick: () => exportKind("thresholds", "threshold-analysis.xlsx"),
                          },
                          { label: t("exportReport"), onClick: () => exportReport("xlsx") },
                        ]}
                      />
                    </div>
                  }
                >
                  <div className="flex flex-wrap items-end gap-8">
                    {result.recommended_lower != null ? (
                      <div>
                        <div className="text-[11px] uppercase tracking-wide text-secondary">
                          Lower limit
                        </div>
                        <div className="text-[30px] font-bold tabular-nums text-primary">
                          {formatNumber(result.recommended_lower, 5)}
                        </div>
                      </div>
                    ) : null}
                    {result.recommended_upper != null ? (
                      <div>
                        <div className="text-[11px] uppercase tracking-wide text-secondary">
                          Upper limit
                        </div>
                        <div className="text-[30px] font-bold tabular-nums text-primary">
                          {formatNumber(result.recommended_upper, 5)}
                        </div>
                      </div>
                    ) : null}
                    {result.class_counts ? (
                      <div className="text-[12px] text-secondary">
                        {Object.entries(result.class_counts).map(([k, v]) => (
                          <div key={k}>
                            {k}: <span className="text-text">{v.toLocaleString()}</span>
                          </div>
                        ))}
                        {result.auc != null ? <div>AUC: {formatNumber(result.auc, 3)}</div> : null}
                      </div>
                    ) : null}
                  </div>
                  <div className="mt-4">
                    <InsightList insights={result.insights} warnings={result.warnings} />
                  </div>
                </SectionCard>

                {supervised && result.recommended ? (
                  <SectionCard
                    title="Current vs recommended"
                    subtitle={
                      result.current
                        ? "Performance of the limit you entered compared with the optimized limit"
                        : "Enter a current limit on the left to compare performance"
                    }
                  >
                    <table className="w-full text-left text-[11.5px]">
                      <thead className="text-secondary">
                        <tr>
                          <th className="py-2">Metric</th>
                          <th className="text-right">Current</th>
                          <th className="text-right">Recommended</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(
                          [
                            ["Limit", (r: ThresholdRow) => formatNumber(r.threshold, 5)],
                            ["False accept (missed defects)", (r: ThresholdRow) => r.fn.toLocaleString()],
                            ["False reject (good rejected)", (r: ThresholdRow) => r.fp.toLocaleString()],
                            ["False accept rate", (r: ThresholdRow) => pct(r.false_accept_rate)],
                            ["False reject rate", (r: ThresholdRow) => pct(r.false_reject_rate)],
                            ["Precision", (r: ThresholdRow) => pct(r.precision)],
                            ["Recall (defect detection)", (r: ThresholdRow) => pct(r.recall)],
                            ["Specificity", (r: ThresholdRow) => pct(r.specificity)],
                            ["Yield", (r: ThresholdRow) => pct(r.yield)],
                            ["Expected cost", (r: ThresholdRow) => formatNumber(r.cost, 5)],
                          ] as [string, (r: ThresholdRow) => string][]
                        ).map(([label, render]) => (
                          <tr key={label} className="border-t border-border/50">
                            <td className="py-1.5 text-text">{label}</td>
                            <td className="text-right tabular-nums">
                              {result.current ? render(result.current) : "—"}
                            </td>
                            <td className="text-right tabular-nums text-primary">
                              {render(result.recommended!)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </SectionCard>
                ) : null}

                {supervised && boundaryData.length ? (
                  <SectionCard
                    title="Defect boundary"
                    subtitle={`Recommended statistical boundary over the labelled class distributions${
                      result.boundary?.overlap_pct != null
                        ? ` · class overlap ≈ ${result.boundary.overlap_pct.toFixed(0)}%`
                        : ""
                    }`}
                  >
                    <div className="h-[300px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <ComposedChart data={boundaryData}>
                          <CartesianGrid stroke="#272D38" strokeDasharray="3 3" />
                          <XAxis dataKey="x" stroke="#8E98A8" fontSize={10} minTickGap={24} />
                          <YAxis stroke="#8E98A8" fontSize={11} />
                          <Tooltip
                            contentStyle={{
                              background: "#191E28",
                              border: "1px solid #272D38",
                              borderRadius: 10,
                              fontSize: 12,
                            }}
                          />
                          <Legend wrapperStyle={{ fontSize: 11 }} />
                          <Area
                            dataKey="ok"
                            name={result.positive_label || "OK"}
                            stroke="#35C759"
                            fill="#35C759"
                            fillOpacity={0.25}
                          />
                          <Area
                            dataKey="ng"
                            name={result.negative_label || "NG"}
                            stroke="#FF4D5F"
                            fill="#FF4D5F"
                            fillOpacity={0.3}
                          />
                          {state.slider != null ? (
                            <ReferenceLine
                              x={Number(state.slider.toPrecision(4))}
                              stroke="#1683FF"
                              strokeWidth={2}
                              label={{ value: "limit", fill: "#1683FF", fontSize: 10 }}
                            />
                          ) : null}
                        </ComposedChart>
                      </ResponsiveContainer>
                    </div>
                    {result.recommended ? (
                      <p className="mt-2 text-[11.5px] text-secondary">
                        {pct(result.recommended.specificity)} of {result.positive_label || "OK"} units are
                        correctly accepted and {pct(result.recommended.recall)} of{" "}
                        {result.negative_label || "NG"} units are correctly detected at the recommended
                        limit.
                      </p>
                    ) : null}
                  </SectionCard>
                ) : null}

                {supervised && result.thresholds?.length ? (
                  <SectionCard
                    title="Threshold trade-off"
                    subtitle="Move the slider to see the effect of a different limit"
                  >
                    <div className="mb-3 space-y-2">
                      <input
                        type="range"
                        className="em-range w-full"
                        min={sliderMin}
                        max={sliderMax}
                        step={step}
                        value={state.slider ?? sliderMin}
                        onChange={(e) => setState({ slider: Number(e.target.value) })}
                      />
                      <div className="flex justify-between text-[11px] text-secondary">
                        <span>{formatNumber(sliderMin, 4)}</span>
                        <span className="text-[13px] font-semibold text-text">
                          Threshold {formatNumber(state.slider, 5)}
                        </span>
                        <span>{formatNumber(sliderMax, 4)}</span>
                      </div>
                    </div>
                    {sliderRow ? (
                      <MetricGrid
                        columns={6}
                        items={[
                          { label: "False accept", value: pct(sliderRow.false_accept_rate), tone: "warning" },
                          { label: "False reject", value: pct(sliderRow.false_reject_rate), tone: "warning" },
                          { label: "Precision", value: pct(sliderRow.precision) },
                          { label: "Recall", value: pct(sliderRow.recall) },
                          { label: "Yield", value: pct(sliderRow.yield), tone: "success" },
                          { label: "Missed defects", value: sliderRow.fn.toLocaleString() },
                          { label: "Rejected units", value: (sliderRow.tp + sliderRow.fp).toLocaleString() },
                          { label: "TP", value: sliderRow.tp.toLocaleString() },
                          { label: "FP", value: sliderRow.fp.toLocaleString() },
                          { label: "FN", value: sliderRow.fn.toLocaleString() },
                          { label: "TN", value: sliderRow.tn.toLocaleString() },
                          { label: "Cost", value: formatNumber(sliderRow.cost, 5) },
                        ]}
                      />
                    ) : null}
                    <div className="mt-4 h-[260px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={thresholdChart}>
                          <CartesianGrid stroke="#272D38" strokeDasharray="3 3" />
                          <XAxis dataKey="threshold" stroke="#8E98A8" fontSize={10} minTickGap={30} />
                          <YAxis stroke="#8E98A8" fontSize={11} unit="%" />
                          <Tooltip
                            contentStyle={{
                              background: "#191E28",
                              border: "1px solid #272D38",
                              borderRadius: 10,
                              fontSize: 12,
                            }}
                          />
                          <Legend wrapperStyle={{ fontSize: 11 }} />
                          <Line
                            dataKey="falseAccept"
                            name="False accept %"
                            stroke="#FF4D5F"
                            dot={false}
                            isAnimationActive={false}
                          />
                          <Line
                            dataKey="falseReject"
                            name="False reject %"
                            stroke="#FFB020"
                            dot={false}
                            isAnimationActive={false}
                          />
                          <Line
                            dataKey="yieldPct"
                            name="Yield %"
                            stroke="#35C759"
                            dot={false}
                            isAnimationActive={false}
                          />
                          {state.slider != null ? (
                            <ReferenceLine
                              x={Number(state.slider.toPrecision(5))}
                              stroke="#1683FF"
                              strokeDasharray="4 4"
                            />
                          ) : null}
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </SectionCard>
                ) : null}

                {supervised && result.roc?.length ? (
                  <SectionCard
                    title="ROC curve"
                    subtitle={`AUC = ${formatNumber(result.auc, 3)}${
                      result.recommended ? ` · Youden J = ${formatNumber(result.recommended.youden, 3)}` : ""
                    }`}
                  >
                    <div className="h-[280px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={result.roc.map((p) => ({ fpr: p.fpr, tpr: p.tpr, ref: p.fpr }))}>
                          <CartesianGrid stroke="#272D38" strokeDasharray="3 3" />
                          <XAxis
                            dataKey="fpr"
                            type="number"
                            domain={[0, 1]}
                            stroke="#8E98A8"
                            fontSize={11}
                            label={{
                              value: "False positive rate",
                              fill: "#8E98A8",
                              fontSize: 10,
                              position: "insideBottom",
                              offset: -2,
                            }}
                          />
                          <YAxis domain={[0, 1]} stroke="#8E98A8" fontSize={11} />
                          <Tooltip
                            contentStyle={{
                              background: "#191E28",
                              border: "1px solid #272D38",
                              borderRadius: 10,
                              fontSize: 12,
                            }}
                          />
                          <Line
                            dataKey="tpr"
                            name="True positive rate"
                            stroke="#1683FF"
                            dot={false}
                            isAnimationActive={false}
                          />
                          <Line
                            dataKey="ref"
                            name="Random"
                            stroke="#272D38"
                            strokeDasharray="4 4"
                            dot={false}
                            isAnimationActive={false}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </SectionCard>
                ) : null}

                {result.statistical ? (
                  <SectionCard
                    title="Statistical limits (distribution based)"
                    subtitle={result.statistical.basis || result.statistical.method}
                  >
                    <MetricGrid
                      columns={5}
                      items={[
                        { label: "Lower", value: formatNumber(result.statistical.lower, 5) },
                        { label: "Upper", value: formatNumber(result.statistical.upper, 5) },
                        { label: "n", value: (result.statistical.n ?? 0).toLocaleString() },
                        {
                          label: "Out of limits",
                          value: (result.statistical.out_of_limits ?? 0).toLocaleString(),
                        },
                        {
                          label: "Out of limits %",
                          value: `${formatNumber(result.statistical.out_of_limits_pct, 3)}%`,
                        },
                      ]}
                    />
                    {!supervised ? (
                      <div className="mt-3">
                        <ValidationNote>{result.statistical.warnings[0]}</ValidationNote>
                      </div>
                    ) : null}
                  </SectionCard>
                ) : null}
              </>
            )}
          </div>
        </div>
      </AnalysisGate>
    </div>
  );
}
