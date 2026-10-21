import { useState } from "react";
import {
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
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
import type { ScatterResult } from "@/lib/analysisTypes";

type ScatterState = {
  x: string;
  y: string;
  groupBy: string;
  result: ScatterResult | null;
  error: string;
};

const DEFAULTS: ScatterState = { x: "", y: "", groupBy: "", result: null, error: "" };
const SERIES_COLORS = ["#1683FF", "#FFB020", "#35C759", "#FF4D5F", "#9B8CFF", "#19C3C3"];

export function ScatterPage() {
  const { t } = useI18n();
  const session = useSession();
  const { capabilities } = session;
  const call = useAnalysisCall();
  const { exportKind, exportReport } = useExport("scatter");
  const [state, setState] = session.moduleState<ScatterState>("scatter", DEFAULTS);
  const [busy, setBusy] = useState(false);

  const measurements = capabilities.measurements;
  const x = state.x && measurements.includes(state.x) ? state.x : measurements[0] || "";
  const y =
    state.y && measurements.includes(state.y) && state.y !== x
      ? state.y
      : measurements.find((m) => m !== x) || "";
  const result = state.result;

  async function analyze() {
    if (!x || !y || x === y) return;
    setBusy(true);
    setState({ error: "" });
    try {
      const res = await call<ScatterResult>("session_scatter", {
        x,
        y,
        group_by: state.groupBy || undefined,
      });
      setState({ result: res, x, y });
      addLog("OK", `Scatter ${x} vs ${y}: n = ${res.n}, r = ${formatNumber(res.r, 3)}.`, "scatter");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setState({ error: msg, result: null });
      addLog("ERROR", msg, "scatter");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader
        title={t("navScatter")}
        subtitle="Relationship between two numeric measurements with regression fit and R²."
      />
      <DatasetBar />
      <AnalysisGate
        ready={capabilities.canScatter}
        requirement="Scatter plot requires at least two usable numeric columns."
      >
        <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
          <div className="space-y-3">
            <SectionCard title="Axes">
              <div className="space-y-3">
                <Field
                  label="X (numeric)"
                  info="Horizontal measurement. Pick the input or the condition you want to relate to the vertical measurement."
                >
                  <Select
                    value={x}
                    onChange={(v) => setState({ x: v })}
                    options={measurements.map((m) => ({ value: m, label: m }))}
                  />
                </Field>
                <Field
                  label="Y (numeric)"
                  info="Vertical measurement. The fit line, r and R² describe how this value moves with X. They do not prove cause."
                >
                  <Select
                    value={y}
                    onChange={(v) => setState({ y: v })}
                    options={measurements.filter((m) => m !== x).map((m) => ({ value: m, label: m }))}
                  />
                </Field>
                <Field
                  label="Group by"
                  hint="optional — colours the points"
                  info="Colour points by a category or by file. Use it to see whether one camera, station or batch follows a different relationship."
                >
                  <Select
                    value={state.groupBy}
                    onChange={(v) => setState({ groupBy: v })}
                    options={[
                      { value: "", label: "No grouping" },
                      { value: "__file", label: t("groupByFile") },
                      ...capabilities.groupings.map((g) => ({ value: g, label: g })),
                    ]}
                  />
                </Field>
                <Button className="w-full" onClick={analyze} disabled={busy || !x || !y}>
                  <Play className="h-4 w-4 fill-current" />
                  {busy ? t("analyzing") : "Plot"}
                </Button>
                {state.error ? <p className="text-[12px] text-error">{state.error}</p> : null}
              </div>
            </SectionCard>
            <PresetBar
              type="scatter"
              config={{ x, y, groupBy: state.groupBy }}
              requiredColumns={["x", "y"]}
              onLoad={(cfg) => setState(cfg as Partial<ScatterState>)}
            />
          </div>

          <div className="min-w-0 space-y-4">
            {!result ? (
              <Card>
                <CardBody className="py-20 text-center text-[13px] text-secondary">
                  Choose X and Y columns and plot the relationship.
                </CardBody>
              </Card>
            ) : (
              <>
                <SectionCard
                  title={`${result.x} vs ${result.y}`}
                  subtitle={
                    result.sampled
                      ? `Visualization sampled: ${result.points.length.toLocaleString()} of ${result.total_points.toLocaleString()} points (statistics use all ${result.n.toLocaleString()} values)`
                      : `${result.n.toLocaleString()} point(s)`
                  }
                  actions={
                    <ExportBar
                      items={[
                        { label: t("exportData"), onClick: () => exportKind("scatter", "scatter.xlsx") },
                        { label: t("exportReport"), onClick: () => exportReport("xlsx") },
                      ]}
                    />
                  }
                >
                  <MetricGrid
                    columns={5}
                    items={[
                      { label: "n", value: result.n.toLocaleString() },
                      { label: "r", value: formatNumber(result.r, 4) },
                      { label: "R²", value: formatNumber(result.r2, 4) },
                      { label: "Slope", value: formatNumber(result.slope, 4) },
                      { label: "Outliers", value: result.outlier_count.toLocaleString() },
                    ]}
                  />
                  <div className="mt-3 h-[360px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <ScatterChart margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
                        <CartesianGrid stroke="#272D38" strokeDasharray="3 3" />
                        <XAxis
                          type="number"
                          dataKey="x"
                          name={result.x}
                          stroke="#8E98A8"
                          fontSize={11}
                          domain={["auto", "auto"]}
                        />
                        <YAxis
                          type="number"
                          dataKey="y"
                          name={result.y}
                          stroke="#8E98A8"
                          fontSize={11}
                          domain={["auto", "auto"]}
                        />
                        <ZAxis range={[14, 14]} />
                        <Tooltip
                          cursor={{ strokeDasharray: "3 3" }}
                          contentStyle={{
                            background: "#191E28",
                            border: "1px solid #272D38",
                            borderRadius: 10,
                            fontSize: 12,
                          }}
                        />
                        {result.series.length ? (
                          result.series.map((s, i) => (
                            <Scatter
                              key={s.name}
                              name={s.name}
                              data={s.points}
                              fill={SERIES_COLORS[i % SERIES_COLORS.length]}
                              isAnimationActive={false}
                            />
                          ))
                        ) : (
                          <Scatter
                            name="points"
                            data={result.points}
                            fill="#1683FF"
                            isAnimationActive={false}
                          />
                        )}
                        {result.fit?.length === 2 ? (
                          <Line
                            name="fit"
                            data={result.fit}
                            dataKey="y"
                            type="linear"
                            stroke="#FFB020"
                            strokeWidth={2}
                            dot={false}
                            isAnimationActive={false}
                          />
                        ) : null}
                      </ScatterChart>
                    </ResponsiveContainer>
                  </div>
                  {result.slope != null && result.intercept != null ? (
                    <p className="mt-2 text-[11.5px] text-secondary">
                      Fit: {result.y} = {formatNumber(result.slope, 4)} × {result.x} +{" "}
                      {formatNumber(result.intercept, 4)}
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
