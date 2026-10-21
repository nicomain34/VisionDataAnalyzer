import { useCallback, useEffect, useState } from "react";
import { FileDown, FileSpreadsheet, FileText } from "lucide-react";
import { PageHeader } from "@/components/ui/PageHeader";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Card, CardBody } from "@/components/ui/Card";
import { DatasetBar, DatasetLoadingCard } from "@/components/analysis/DatasetBar";
import { SectionCard, ValidationNote } from "@/components/analysis/Controls";
import { useI18n } from "@/lib/i18n";
import { useAnalysisCall, useSession } from "@/lib/analysisSession";
import { useExport } from "@/lib/analysisExport";

type Section = { id: string; label: string; hint: string; exportKind?: string; file: string };

const SECTIONS: Section[] = [
  { id: "dataset", label: "Dataset information", hint: "Source, files, rows, columns", file: "dataset.xlsx" },
  {
    id: "quality",
    label: "Data quality",
    hint: "Issues, missing values, failed files",
    exportKind: "quality",
    file: "data-quality.xlsx",
  },
  {
    id: "schema",
    label: "Detected schema",
    hint: "Column types, roles and exclusions",
    exportKind: "schema",
    file: "schema.xlsx",
  },
  {
    id: "distribution",
    label: "Distribution statistics",
    hint: "Requires a Distribution run",
    exportKind: "statistics",
    file: "distribution-statistics.xlsx",
  },
  {
    id: "outliers",
    label: "Outliers",
    hint: "Requires a Distribution run",
    exportKind: "outliers",
    file: "outliers.xlsx",
  },
  {
    id: "comparison",
    label: "Group comparison",
    hint: "Requires a Comparison run",
    exportKind: "comparison",
    file: "comparison.xlsx",
  },
  {
    id: "correlation",
    label: "Correlation",
    hint: "Requires a Correlation run",
    exportKind: "correlation",
    file: "correlation.xlsx",
  },
  {
    id: "scatter",
    label: "Scatter / regression",
    hint: "Requires a Scatter run",
    exportKind: "scatter",
    file: "scatter.xlsx",
  },
  {
    id: "trend",
    label: "Time trend",
    hint: "Requires a Time Trend run",
    exportKind: "trend",
    file: "time-trend.xlsx",
  },
  {
    id: "batch",
    label: "Batch / file comparison",
    hint: "Requires a Batch comparison run",
    exportKind: "batch",
    file: "batch-comparison.xlsx",
  },
  {
    id: "limit",
    label: "Limit recommendation",
    hint: "Requires a Limit Finder run",
    exportKind: "thresholds",
    file: "threshold-analysis.xlsx",
  },
];

const ALWAYS_AVAILABLE = new Set(["dataset", "quality", "schema"]);

export function ReportsPage() {
  const { t } = useI18n();
  const { profile, status } = useSession();
  const call = useAnalysisCall();
  const { exportKind, exportReport } = useExport("reports");
  const [available, setAvailable] = useState<string[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    if (!profile) {
      setAvailable([]);
      return;
    }
    try {
      const res = await call<{ available: string[] }>("session_results", {});
      setAvailable(res.available);
    } catch {
      setAvailable([]);
    }
  }, [call, profile]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  function isReady(section: Section) {
    return ALWAYS_AVAILABLE.has(section.id) || available.includes(section.id === "outliers" ? "distribution" : section.id);
  }

  function toggle(id: string) {
    setSelected((prev) => (prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]));
  }

  async function build(format: "xlsx" | "html") {
    setBusy(true);
    try {
      await exportReport(format, selected.length ? selected : undefined);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader
        title={t("navReports")}
        subtitle="Export any single analysis or build a full engineering report from the results currently calculated."
      />
      <DatasetBar />

      {status === "loading" ? (
        <DatasetLoadingCard />
      ) : !profile ? (
        <Card>
          <CardBody className="py-14 text-center text-[13px] text-secondary">
            Load a dataset to export analyses.
          </CardBody>
        </Card>
      ) : (
        <div className="space-y-4">
          <SectionCard
            title="Full report"
            subtitle="Built from the values already shown in the UI — nothing is recalculated."
            actions={
              <div className="flex gap-2">
                <Button variant="secondary" onClick={() => void refresh()}>
                  Refresh availability
                </Button>
                <Button onClick={() => void build("xlsx")} disabled={busy}>
                  <FileSpreadsheet className="h-4 w-4" />
                  Excel report
                </Button>
                <Button variant="secondary" onClick={() => void build("html")} disabled={busy}>
                  <FileText className="h-4 w-4" />
                  Printable report (PDF)
                </Button>
              </div>
            }
          >
            <p className="mb-3 text-[12px] text-secondary">
              {selected.length
                ? `${selected.length} section(s) selected.`
                : "No selection — every section with calculated results will be included."}
            </p>
            <ValidationNote>
              The printable report opens in a browser; use the browser print dialog and choose
              &quot;Save as PDF&quot; to produce a PDF file.
            </ValidationNote>
          </SectionCard>

          <SectionCard
            title="Sections"
            subtitle="Select the sections for the full report, or export any one of them on its own."
          >
            <table className="w-full text-left text-[12px]">
              <thead className="text-secondary">
                <tr>
                  <th className="py-2 pr-2">Include</th>
                  <th>Section</th>
                  <th>Status</th>
                  <th className="text-right">Single export</th>
                </tr>
              </thead>
              <tbody>
                {SECTIONS.map((s) => {
                  const ready = isReady(s);
                  return (
                    <tr key={s.id} className="border-t border-border/50">
                      <td className="py-2 pr-2">
                        <input
                          type="checkbox"
                          className="em-check"
                          checked={selected.includes(s.id)}
                          disabled={!ready}
                          onChange={() => toggle(s.id)}
                        />
                      </td>
                      <td>
                        <div className="text-text">{s.label}</div>
                        <div className="text-[11px] text-secondary">{s.hint}</div>
                      </td>
                      <td>
                        <Badge tone={ready ? "success" : "muted"}>
                          {ready ? "Available" : "Not calculated"}
                        </Badge>
                      </td>
                      <td className="text-right">
                        {s.exportKind ? (
                          <div className="inline-flex gap-1">
                            <Button
                              size="sm"
                              variant="ghost"
                              disabled={!ready}
                              onClick={() => exportKind(s.exportKind!, s.file)}
                            >
                              <FileDown className="h-3.5 w-3.5" />
                              XLSX
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              disabled={!ready}
                              onClick={() => exportKind(s.exportKind!, s.file.replace(".xlsx", ".csv"))}
                            >
                              CSV
                            </Button>
                          </div>
                        ) : (
                          <span className="text-secondary">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </SectionCard>
        </div>
      )}
    </div>
  );
}
