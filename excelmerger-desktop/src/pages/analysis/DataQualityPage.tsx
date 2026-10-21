import { useMemo, useState } from "react";
import { PageHeader } from "@/components/ui/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Card, CardBody } from "@/components/ui/Card";
import { DatasetBar, DatasetLoadingCard } from "@/components/analysis/DatasetBar";
import { ExportBar, MetricGrid, SectionCard, Select } from "@/components/analysis/Controls";
import { useI18n } from "@/lib/i18n";
import { useSession } from "@/lib/analysisSession";
import { useExport } from "@/lib/analysisExport";
import { cn, formatNumber } from "@/lib/utils";

export function DataQualityPage() {
  const { t } = useI18n();
  const { profile, status } = useSession();
  const { exportKind, exportReport } = useExport("quality");
  const [severity, setSeverity] = useState("ALL");
  const [query, setQuery] = useState("");

  const issues = useMemo(() => {
    const list = profile?.issues ?? [];
    const q = query.trim().toLowerCase();
    return list.filter(
      (i) =>
        (severity === "ALL" || i.severity === severity) &&
        (!q ||
          `${i.file} ${i.column} ${i.issue} ${i.details}`.toLowerCase().includes(q)),
    );
  }, [profile, severity, query]);

  const counts = useMemo(() => {
    const list = profile?.issues ?? [];
    return {
      ERROR: list.filter((i) => i.severity === "ERROR").length,
      WARNING: list.filter((i) => i.severity === "WARNING").length,
      INFO: list.filter((i) => i.severity === "INFO").length,
    };
  }, [profile]);

  return (
    <div>
      <PageHeader
        title={t("navDataQuality")}
        subtitle="Schema consistency, missing and invalid values, duplicates and unreadable files."
      />
      <DatasetBar />

      {status === "loading" ? (
        <DatasetLoadingCard />
      ) : !profile ? (
        <Card>
          <CardBody className="py-14 text-center text-[13px] text-secondary">
            Load a dataset to inspect its quality.
          </CardBody>
        </Card>
      ) : (
        <div className="space-y-4">
          <SectionCard
            title="Quality summary"
            actions={
              <ExportBar
                items={[
                  { label: "Export issues", onClick: () => exportKind("quality", "data-quality.xlsx") },
                  { label: t("exportReport"), onClick: () => exportReport("xlsx") },
                ]}
              />
            }
          >
            <MetricGrid
              columns={6}
              items={[
                { label: "Files scanned", value: profile.files_scanned },
                { label: "Valid files", value: profile.valid_files, tone: "success" },
                {
                  label: "Failed files",
                  value: profile.failed_files,
                  tone: profile.failed_files ? "error" : "default",
                },
                { label: "Rows", value: profile.rows.toLocaleString() },
                { label: "Columns", value: profile.total_columns },
                { label: "Missing", value: `${formatNumber(profile.missing_pct, 3)}%` },
                { label: "Duplicate rows", value: `${formatNumber(profile.duplicate_pct, 3)}%` },
                { label: "Invalid values", value: profile.invalid_values.toLocaleString() },
                { label: "Empty columns", value: profile.empty_columns },
                { label: "Mixed-type columns", value: profile.mixed_columns },
                { label: "Unnamed columns", value: profile.unnamed_columns },
                {
                  label: "Errors",
                  value: counts.ERROR,
                  tone: counts.ERROR ? "error" : "default",
                },
              ]}
            />
            {profile.failed_files > 0 ? (
              <p className="mt-3 text-[12px] text-warning">
                Files processed: {profile.files_scanned} · successful: {profile.valid_files} · failed:{" "}
                {profile.failed_files}
                {profile.failed_file_names.length
                  ? ` (${profile.failed_file_names.slice(0, 5).join(", ")}${
                      profile.failed_file_names.length > 5 ? "…" : ""
                    })`
                  : ""}
              </p>
            ) : null}
          </SectionCard>

          <SectionCard
            title={`Issues (${issues.length})`}
            subtitle={`${counts.ERROR} error(s) · ${counts.WARNING} warning(s) · ${counts.INFO} info`}
            actions={
              <div className="flex gap-2">
                <Select
                  className="w-32"
                  value={severity}
                  onChange={setSeverity}
                  options={[
                    { value: "ALL", label: "All severities" },
                    { value: "ERROR", label: "Error" },
                    { value: "WARNING", label: "Warning" },
                    { value: "INFO", label: "Info" },
                  ]}
                />
                <input
                  className="h-9 w-48 rounded-lg border border-border bg-bg px-2 text-[12px] text-text"
                  placeholder="Search issues…"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </div>
            }
            bodyClassName="max-h-[30rem] overflow-auto"
          >
            {!issues.length ? (
              <p className="py-6 text-center text-[13px] text-secondary">
                No issues match the current filter.
              </p>
            ) : (
              <table className="w-full text-left text-[11.5px]">
                <thead className="sticky top-0 bg-card text-secondary">
                  <tr>
                    <th className="py-2">Severity</th>
                    <th>File</th>
                    <th>Column</th>
                    <th>Issue</th>
                    <th className="text-right">Count</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {issues.map((iss, i) => (
                    <tr key={`${iss.file}-${iss.column}-${iss.issue}-${i}`} className="border-t border-border/50">
                      <td className="py-1.5">
                        <Badge
                          tone={
                            iss.severity === "ERROR"
                              ? "error"
                              : iss.severity === "WARNING"
                                ? "warning"
                                : "muted"
                          }
                        >
                          {iss.severity}
                        </Badge>
                      </td>
                      <td
                        className={cn(
                          "max-w-[200px] truncate",
                          iss.severity === "ERROR" && "text-error",
                        )}
                      >
                        {iss.file}
                      </td>
                      <td className="max-w-[180px] truncate">{iss.column || "—"}</td>
                      <td>{iss.issue}</td>
                      <td className="text-right tabular-nums">{iss.count.toLocaleString()}</td>
                      <td className="max-w-[260px] truncate text-secondary">{iss.details}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </SectionCard>

          {profile.excluded_columns.length ? (
            <SectionCard
              title={`Columns excluded from analysis candidates (${profile.excluded_columns.length})`}
              subtitle="Source data is never modified — these columns are only kept out of the analysis pickers."
              bodyClassName="max-h-60 overflow-auto"
            >
              <table className="w-full text-left text-[11.5px]">
                <thead className="sticky top-0 bg-card text-secondary">
                  <tr>
                    <th className="py-2">Column</th>
                    <th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {profile.excluded_columns.map((c) => (
                    <tr key={c.name} className="border-t border-border/50">
                      <td className="max-w-[260px] truncate py-1.5 text-text">{c.name}</td>
                      <td className="text-secondary">{c.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </SectionCard>
          ) : null}
        </div>
      )}
    </div>
  );
}
