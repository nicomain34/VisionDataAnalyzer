import { useMemo, useState } from "react";
import { PageHeader } from "@/components/ui/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Card, CardBody } from "@/components/ui/Card";
import { DatasetBar, DatasetLoadingCard } from "@/components/analysis/DatasetBar";
import {
  ExportBar,
  InsightList,
  MetricGrid,
  SectionCard,
} from "@/components/analysis/Controls";
import { useI18n } from "@/lib/i18n";
import { useSession } from "@/lib/analysisSession";
import { useExport } from "@/lib/analysisExport";
import { cn, formatNumber } from "@/lib/utils";
import type { ColumnSchema } from "@/lib/analysisTypes";

function typeTone(t: string): "primary" | "success" | "warning" | "error" | "muted" {
  if (t === "numeric") return "primary";
  if (t === "categorical" || t === "boolean") return "success";
  if (t === "datetime") return "primary";
  if (t === "mixed") return "warning";
  if (t === "empty") return "error";
  return "muted";
}

export function OverviewPage() {
  const { t } = useI18n();
  const { profile, status } = useSession();
  const { exportKind, exportReport } = useExport("overview");
  const [onlyUsable, setOnlyUsable] = useState(false);

  const columns = useMemo(() => {
    const list: ColumnSchema[] = profile?.columns ?? [];
    return onlyUsable ? list.filter((c) => c.usable_for_analysis) : list;
  }, [profile, onlyUsable]);

  const tc = profile?.type_counts ?? {};

  return (
    <div>
      <PageHeader title={t("overviewTitle")} subtitle={t("overviewSubtitle")} />
      <DatasetBar />

      {status === "loading" ? (
        <DatasetLoadingCard />
      ) : !profile ? (
        <Card>
          <CardBody className="py-14 text-center text-[13px] text-secondary">
            No dataset is loaded yet. Choose a folder or individual Excel/CSV files above — the scan
            runs once and is shared by all analysis modules.
          </CardBody>
        </Card>
      ) : (
        <div className="space-y-4">
          <SectionCard
            title="Dataset summary"
            subtitle={profile.source_folder || `${profile.source_file_count ?? 0} selected file(s)`}
            actions={
              <ExportBar
                items={[
                  { label: "Schema", onClick: () => exportKind("schema", "schema.xlsx") },
                  { label: "Report", onClick: () => exportReport("xlsx") },
                ]}
              />
            }
          >
            <MetricGrid
              columns={6}
              items={[
                { label: "Files", value: profile.files_scanned },
                { label: "Valid files", value: profile.valid_files, tone: "success" },
                {
                  label: "Failed files",
                  value: profile.failed_files,
                  tone: profile.failed_files ? "error" : "default",
                },
                { label: "Rows", value: profile.rows.toLocaleString() },
                { label: "Columns", value: profile.total_columns },
                { label: "Size", value: profile.total_size || "—" },
                { label: "Numeric", value: tc.numeric ?? 0 },
                { label: "Categorical", value: tc.categorical ?? 0 },
                { label: "Date/Time", value: tc.datetime ?? 0 },
                { label: "Identifier", value: tc.identifier ?? 0 },
                { label: "Boolean", value: tc.boolean ?? 0 },
                { label: "Text", value: tc.text ?? 0 },
              ]}
            />
            {profile.failed_files > 0 ? (
              <p className="mt-3 text-[12px] text-warning">
                {profile.failed_files} file(s) could not be processed. Analysis continued with the
                remaining {profile.valid_files} file(s) — see Data Quality for details.
              </p>
            ) : null}
          </SectionCard>

          <div className="grid gap-4 xl:grid-cols-2">
            <SectionCard title="Data quality summary">
              <MetricGrid
                columns={3}
                items={[
                  {
                    label: "Missing values",
                    value: `${formatNumber(profile.missing_pct, 3)}%`,
                    tone: profile.missing_pct > 5 ? "warning" : "default",
                  },
                  { label: "Invalid values", value: profile.invalid_values.toLocaleString() },
                  {
                    label: "Duplicate rows",
                    value: `${formatNumber(profile.duplicate_pct, 3)}%`,
                    tone: profile.duplicate_pct > 1 ? "warning" : "default",
                  },
                  { label: "Empty columns", value: profile.empty_columns },
                  { label: "Mixed-type columns", value: profile.mixed_columns },
                  { label: "Open issues", value: profile.issues.length },
                ]}
              />
            </SectionCard>

            <SectionCard
              title="Schema summary"
              subtitle={`${profile.numeric_columns.length} measurement column(s) are offered for analysis`}
            >
              <MetricGrid
                columns={3}
                items={[
                  { label: "Measurements", value: profile.numeric_columns.length },
                  { label: "Grouping", value: profile.grouping_columns.length },
                  { label: "Date/Time", value: profile.datetime_columns.length },
                  { label: "Identifiers", value: profile.identifier_columns.length },
                  { label: "Label candidates", value: profile.label_columns.length },
                  { label: "Excluded", value: profile.excluded_columns.length },
                ]}
              />
              {profile.excluded_columns.length ? (
                <div className="mt-3 max-h-24 overflow-auto text-[11.5px] text-secondary">
                  {profile.excluded_columns.slice(0, 20).map((c) => (
                    <div key={c.name} className="truncate">
                      <span className="text-text">{c.name}</span> — {c.reason}
                    </div>
                  ))}
                </div>
              ) : null}
            </SectionCard>
          </div>

          <SectionCard title="Quick insights">
            <InsightList insights={profile.insights} />
          </SectionCard>

          <SectionCard
            title={`Detected columns (${columns.length})`}
            actions={
              <label className="flex items-center gap-2 text-[11.5px] text-secondary">
                <input
                  type="checkbox"
                  className="em-check"
                  checked={onlyUsable}
                  onChange={(e) => setOnlyUsable(e.target.checked)}
                />
                Analysis candidates only
              </label>
            }
            bodyClassName="max-h-[30rem] overflow-auto"
          >
            <table className="w-full text-left text-[11.5px]">
              <thead className="sticky top-0 bg-card text-secondary">
                <tr>
                  <th className="py-2">Column</th>
                  <th>Type</th>
                  <th className="text-right">Values</th>
                  <th className="text-right">Unique</th>
                  <th className="text-right">Missing</th>
                  <th className="text-right">Min</th>
                  <th className="text-right">Max</th>
                  <th className="text-right">Mean</th>
                  <th>Coverage</th>
                  <th>Role</th>
                </tr>
              </thead>
              <tbody>
                {columns.map((c) => (
                  <tr
                    key={c.name}
                    className={cn(
                      "border-t border-border/50",
                      !c.usable_for_analysis && "text-secondary",
                    )}
                  >
                    <td className="max-w-[220px] truncate py-1.5 font-medium text-text">{c.name}</td>
                    <td>
                      <Badge tone={typeTone(String(c.col_type))}>{String(c.col_type)}</Badge>
                    </td>
                    <td className="text-right tabular-nums">{(c.count ?? 0).toLocaleString()}</td>
                    <td className="text-right tabular-nums">{(c.cardinality ?? 0).toLocaleString()}</td>
                    <td className="text-right tabular-nums">
                      {(c.missing ?? 0).toLocaleString()} ({formatNumber(c.missing_pct, 2)}%)
                    </td>
                    <td className="text-right tabular-nums">{formatNumber(c.min, 4)}</td>
                    <td className="text-right tabular-nums">{formatNumber(c.max, 4)}</td>
                    <td className="text-right tabular-nums">{formatNumber(c.mean, 4)}</td>
                    <td>
                      {c.file_count < profile.files_scanned
                        ? `${c.file_count} of ${profile.files_scanned} files`
                        : `all ${profile.files_scanned}`}
                    </td>
                    <td className="max-w-[180px] truncate">
                      {c.usable_for_analysis ? (
                        <span className="text-text">{c.analysis_role}</span>
                      ) : (
                        <span title={c.reason_excluded}>{c.reason_excluded || "excluded"}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </SectionCard>
        </div>
      )}
    </div>
  );
}
