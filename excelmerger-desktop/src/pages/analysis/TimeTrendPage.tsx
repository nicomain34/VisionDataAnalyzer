import { useMemo, useState } from "react";
import {
  CartesianGrid,
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
import { Card, CardBody } from "@/components/ui/Card";
import { DatasetBar, AnalysisGate } from "@/components/analysis/DatasetBar";
import { PresetBar } from "@/components/analysis/PresetBar";
import {
  ExportBar,
  Field,
  InsightList,
  MetricGrid,
  SectionCard,
  Select,
} from "@/components/analysis/Controls";
import { useI18n } from "@/lib/i18n";
import { useAnalysisCall, useSession } from "@/lib/analysisSession";
import { useExport } from "@/lib/analysisExport";
import { addLog } from "@/lib/logStore";
import { formatNumber } from "@/lib/utils";
import type { TrendResult } from "@/lib/analysisTypes";

type TrendState = {
  timeCol: string;
  valueCol: string;
  aggregation: string;
  from: string;
  to: string;
  result: TrendResult | null;
  error: string;
};

const DEFAULTS: TrendState = {
  timeCol: "",
  valueCol: "",
  aggregation: "daily",
  from: "",
  to: "",
  result: null,
  error: "",
};

export function TimeTrendPage() {
  const { t } = useI18n();
  const session = useSession();
  const { capabilities } = session;
  const call = useAnalysisCall();
  const { exportKind, exportReport } = useExport("trend");
  const [state, setState] = session.moduleState<TrendState>("trend", DEFAULTS);
  const [busy, setBusy] = useState(false);

  const timeCol =
    state.timeCol && capabilities.datetimes.includes(state.timeCol)
      ? state.timeCol
      : capabilities.datetimes[0] || "";
  const valueCol =
    state.valueCol && capabilities.measurements.includes(state.valueCol)
      ? state.valueCol
      : capabilities.measurements[0] || "";
  const result = state.result;

  async function analyze() {
    if (!timeCol || !valueCol) return;
    setBusy(true);
    setState({ error: "" });
    try {
      const res = await call<TrendResult>("session_trend", {
        time_col: timeCol,
        value_col: valueCol,
        aggregation: state.aggregation,
        date_from: state.from || undefined,
        date_to: state.to || undefined,
      });
      setState({ result: res, timeCol, valueCol });
      addLog("OK", `Time trend ${valueCol} (${res.aggregation}): ${res.n} point(s).`, "trend");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setState({ error: msg, result: null });
      addLog("ERROR", msg, "trend");
    } finally {
      setBusy(false);
    }
  }

  const chartData = useMemo(
    () =>
      (result?.points || []).map((p) => ({
        t: p.t.length > 19 ? p.t.slice(0, 19).replace("T", " ") : p.t.replace("T", " "),
        v: p.v,
        roll: p.roll,
        outlier: p.outlier,
      })),
    [result],
  );

  return (
    <div>
      <PageHeader
        title={t("navTrend")}
        subtitle="Measurement behaviour over a detected Date/Time column with rolling mean and outliers."
      />
      <DatasetBar />
      <AnalysisGate
        ready={capabilities.canTrend}
        requirement="Time Trend requires a valid Date/Time column and a numeric measurement. No Date/Time column was detected in this dataset."
      >
        <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
          <div className="space-y-3">
            <SectionCard title="Series">
              <div className="space-y-3">
                <Field
                  label="Timestamp"
                  info="Column detected as date and time. Compact values such as 2026-10-0700-11-52 are accepted."
                >
                  <Select
                    value={timeCol}
                    onChange={(v) => setState({ timeCol: v })}
                    options={capabilities.datetimes.map((c) => ({ value: c, label: c }))}
                  />
                </Field>
                <Field
                  label="Value"
                  info="Numeric measurement plotted against time. Statistics use every valid point, even when the chart is sampled."
                >
                  <Select
                    value={valueCol}
                    onChange={(v) => setState({ valueCol: v })}
                    options={capabilities.measurements.map((c) => ({ value: c, label: c }))}
                  />
                </Field>
                <Field
                  label="Aggregation"
                  info="Raw shows individual points. Hourly, daily, weekly and shift average them so a slow drift is easier to see than single-piece noise."
                >
                  <Select
                    value={state.aggregation}
                    onChange={(v) => setState({ aggregation: v })}
                    options={[
                      { value: "raw", label: "Raw" },
                      { value: "hourly", label: "Hourly" },
                      { value: "daily", label: "Daily" },
                      { value: "weekly", label: "Weekly" },
                      { value: "shift", label: "Shift" },
                    ]}
                  />
                </Field>
                <div className="grid grid-cols-2 gap-2">
                  <Field label="From" info="Ignore points before this date. Leave empty to start at the first timestamp.">
                    <input
                      type="date"
                      className="h-9 w-full rounded-lg border border-border bg-bg px-2 text-[12px] text-text"
                      value={state.from}
                      onChange={(e) => setState({ from: e.target.value })}
                    />
                  </Field>
                  <Field label="To" info="Ignore points after this date. Leave empty to include the latest timestamp.">
                    <input
                      type="date"
                      className="h-9 w-full rounded-lg border border-border bg-bg px-2 text-[12px] text-text"
                      value={state.to}
                      onChange={(e) => setState({ to: e.target.value })}
                    />
                  </Field>
                </div>
                <Button className="w-full" onClick={analyze} disabled={busy || !timeCol || !valueCol}>
                  <Play className="h-4 w-4 fill-current" />
                  {busy ? t("analyzing") : "Run"}
                </Button>
                {state.error ? <p className="text-[12px] text-error">{state.error}</p> : null}
              </div>
            </SectionCard>
            <PresetBar
              type="trend"
              config={{
                timeCol,
                valueCol,
                aggregation: state.aggregation,
                from: state.from,
                to: state.to,
              }}
              requiredColumns={["timeCol", "valueCol"]}
              onLoad={(cfg) => setState(cfg as Partial<TrendState>)}
            />
          </div>

          <div className="min-w-0 space-y-4">
            {!result ? (
              <Card>
                <CardBody className="py-20 text-center text-[13px] text-secondary">
                  Select a timestamp and value column, then run the trend analysis.
                </CardBody>
              </Card>
            ) : (
              <>
                <SectionCard
                  title={`${result.value_col} over ${result.time_col}`}
                  subtitle={
                    result.range
                      ? `${result.range.from.slice(0, 19)} … ${result.range.to.slice(0, 19)} · ${result.aggregation}`
                      : result.aggregation
                  }
                  actions={
                    <ExportBar
                      items={[
                        { label: t("exportData"), onClick: () => exportKind("trend", "time-trend.xlsx") },
                        { label: t("exportReport"), onClick: () => exportReport("xlsx") },
                      ]}
                    />
                  }
                >
                  <MetricGrid
                    columns={5}
                    items={[
                      { label: "n", value: result.n.toLocaleString() },
                      { label: "Mean", value: formatNumber(result.stats?.mean, 4) },
                      { label: "Min", value: formatNumber(result.stats?.min, 4) },
                      { label: "Max", value: formatNumber(result.stats?.max, 4) },
                      { label: "Outliers", value: (result.outlier_count ?? 0).toLocaleString() },
                    ]}
                  />
                  <div className="mt-3 h-[340px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={chartData}>
                        <CartesianGrid stroke="#272D38" strokeDasharray="3 3" />
                        <XAxis
                          dataKey="t"
                          stroke="#8E98A8"
                          fontSize={10}
                          minTickGap={40}
                          interval="preserveStartEnd"
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
                        <Line
                          type="monotone"
                          dataKey="v"
                          name="Value"
                          stroke="#1683FF"
                          dot={false}
                          isAnimationActive={false}
                        />
                        <Line
                          type="monotone"
                          dataKey="roll"
                          name="Rolling mean"
                          stroke="#FFB020"
                          dot={false}
                          isAnimationActive={false}
                        />
                        {result.stats?.min != null ? (
                          <ReferenceLine y={result.stats.min} stroke="#272D38" strokeDasharray="3 3" />
                        ) : null}
                        {result.stats?.max != null ? (
                          <ReferenceLine y={result.stats.max} stroke="#272D38" strokeDasharray="3 3" />
                        ) : null}
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                  {result.sampled ? (
                    <p className="mt-2 text-[11.5px] text-secondary">
                      Visualization sampled: {result.points.length.toLocaleString()} of{" "}
                      {(result.total_points ?? 0).toLocaleString()} points.
                    </p>
                  ) : null}
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
