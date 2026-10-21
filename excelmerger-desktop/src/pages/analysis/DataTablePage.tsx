import { useCallback, useEffect, useMemo, useState } from "react";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { DatasetBar, DatasetLoadingCard } from "@/components/analysis/DatasetBar";
import { Progress } from "@/components/ui/Progress";
import { ExportBar, SectionCard } from "@/components/analysis/Controls";
import { useI18n } from "@/lib/i18n";
import { useAnalysisCall, useSession } from "@/lib/analysisSession";
import { useExport } from "@/lib/analysisExport";
import { addLog } from "@/lib/logStore";
import { cn } from "@/lib/utils";
import type { TablePage } from "@/lib/analysisTypes";

type TableState = {
  page: number;
  pageSize: number;
  query: string;
  sortKey: string;
  sortDir: "asc" | "desc";
  hidden: string[];
  candidatesOnly: boolean;
};

const DEFAULTS: TableState = {
  page: 0,
  pageSize: 100,
  query: "",
  sortKey: "",
  sortDir: "asc",
  hidden: [],
  candidatesOnly: true,
};

/**
 * Rows are paginated by the engine: only one page is ever held in React state,
 * so the DOM never receives the whole dataset.
 */
export function DataTablePage() {
  const { t } = useI18n();
  const session = useSession();
  const { profile } = session;
  const call = useAnalysisCall();
  const { exportKind } = useExport("datatable");
  const [state, setState] = session.moduleState<TableState>("table", DEFAULTS);
  const [data, setData] = useState<TablePage | null>(null);
  const [colQuery, setColQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const allColumns = useMemo(() => {
    const cols = profile?.columns ?? [];
    return {
      all: cols.map((c) => c.name),
      usable: cols.filter((c) => c.usable_for_analysis).map((c) => c.name),
      noisy: cols.filter((c) => !c.usable_for_analysis).map((c) => c.name),
    };
  }, [profile]);

  const requestedColumns = useMemo(() => {
    const base = state.candidatesOnly ? allColumns.usable : allColumns.all;
    return base.filter((c) => !state.hidden.includes(c));
  }, [allColumns, state.candidatesOnly, state.hidden]);

  const load = useCallback(async () => {
    if (!profile) {
      setData(null);
      return;
    }
    setBusy(true);
    setError("");
    try {
      const res = await call<TablePage>("session_table", {
        offset: state.page * state.pageSize,
        limit: state.pageSize,
        columns: requestedColumns.length ? requestedColumns : undefined,
        query: state.query || undefined,
        sort_by: state.sortKey || undefined,
        sort_dir: state.sortDir,
      });
      setData(res);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      addLog("ERROR", msg, "datatable");
    } finally {
      setBusy(false);
    }
  }, [
    call,
    profile,
    requestedColumns,
    state.page,
    state.pageSize,
    state.query,
    state.sortKey,
    state.sortDir,
  ]);

  useEffect(() => {
    void load();
  }, [load]);

  const visibleColumnChips = useMemo(() => {
    const q = colQuery.trim().toLowerCase();
    const base = state.candidatesOnly ? allColumns.usable : allColumns.all;
    return q ? base.filter((c) => c.toLowerCase().includes(q)) : base;
  }, [allColumns, state.candidatesOnly, colQuery]);

  const totalPages = data ? Math.max(1, Math.ceil(data.total / state.pageSize)) : 1;

  function toggleSort(c: string) {
    if (state.sortKey === c) {
      setState({ sortDir: state.sortDir === "asc" ? "desc" : "asc", page: 0 });
    } else {
      setState({ sortKey: c, sortDir: "asc", page: 0 });
    }
  }

  function toggleColumn(c: string) {
    setState({
      hidden: state.hidden.includes(c) ? state.hidden.filter((h) => h !== c) : [...state.hidden, c],
    });
  }

  return (
    <div>
      <PageHeader
        title={t("navDataTable")}
        subtitle="Paginated view of the loaded dataset. Only the current page is rendered."
      />
      <DatasetBar />

      {session.status === "loading" ? (
        <DatasetLoadingCard />
      ) : !profile ? (
        <Card>
          <CardBody className="py-14 text-center text-[13px] text-secondary">
            {t("emptyAnalysis")}
          </CardBody>
        </Card>
      ) : (
        <div className="space-y-4">
          <SectionCard
            title="Columns"
            subtitle={
              state.candidatesOnly && allColumns.noisy.length
                ? `${allColumns.noisy.length} import-noise column(s) hidden (unnamed, empty, metadata). Source files are unchanged.`
                : `${allColumns.all.length} column(s) in the dataset`
            }
            actions={
              <div className="flex items-center gap-2">
                <label className="flex items-center gap-2 text-[11.5px] text-secondary">
                  <input
                    type="checkbox"
                    className="em-check"
                    checked={state.candidatesOnly}
                    onChange={(e) => setState({ candidatesOnly: e.target.checked, page: 0 })}
                  />
                  Analysis columns only
                </label>
                <input
                  className="h-9 w-40 rounded-lg border border-border bg-bg px-2 text-[12px] text-text"
                  placeholder="Find column…"
                  value={colQuery}
                  onChange={(e) => setColQuery(e.target.value)}
                />
              </div>
            }
            bodyClassName="max-h-40 overflow-auto"
          >
            <div className="flex flex-wrap gap-x-4 gap-y-1">
              {visibleColumnChips.map((c) => (
                <label key={c} className="flex items-center gap-1.5 text-[11px] text-secondary">
                  <input
                    type="checkbox"
                    className="em-check"
                    checked={!state.hidden.includes(c)}
                    onChange={() => toggleColumn(c)}
                  />
                  {c}
                </label>
              ))}
            </div>
          </SectionCard>

          <SectionCard
            title={
              data
                ? `${data.total.toLocaleString()} row(s) · page ${state.page + 1} / ${totalPages}`
                : "Reading rows"
            }
            actions={
              <div className="flex gap-2">
                <input
                  className="h-9 w-48 rounded-lg border border-border bg-bg px-2 text-[12px] text-text"
                  placeholder="Search rows…"
                  value={state.query}
                  onChange={(e) => setState({ query: e.target.value, page: 0 })}
                />
                <select
                  className="h-9 rounded-lg border border-border bg-bg px-2 text-[12px] text-text"
                  value={state.pageSize}
                  onChange={(e) => setState({ pageSize: Number(e.target.value), page: 0 })}
                >
                  {[50, 100, 250, 500].map((n) => (
                    <option key={n} value={n}>
                      {n} / page
                    </option>
                  ))}
                </select>
                <ExportBar
                  items={[
                    { label: "Export page (CSV)", onClick: () => exportKind("table", "table-page.csv") },
                    { label: t("exportData"), onClick: () => exportKind("table", "table-page.xlsx") },
                  ]}
                />
              </div>
            }
            bodyClassName="overflow-auto"
          >
            {busy && !data ? (
              <div className="px-1 py-8">
                <Progress value={0} max={1} indeterminate />
              </div>
            ) : null}
            {error ? <p className="py-6 text-center text-[12px] text-error">{error}</p> : null}
            {!error && data?.rows.length ? (
              <>
                <table className="w-full text-left text-[11.5px]">
                  <thead className="sticky top-0 bg-card text-secondary">
                    <tr>
                      {data.columns.map((c) => (
                        <th key={c} className="px-2 py-2 font-semibold">
                          <button type="button" onClick={() => toggleSort(c)} className="truncate">
                            {c}
                            {state.sortKey === c ? (state.sortDir === "asc" ? " ↑" : " ↓") : ""}
                          </button>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.rows.map((row, i) => (
                      <tr key={state.page * state.pageSize + i} className="border-t border-border/50">
                        {data.columns.map((c) => {
                          const raw = row[c];
                          const missing = raw == null || String(raw).trim() === "";
                          return (
                            <td
                              key={c}
                              className={cn(
                                "max-w-[220px] truncate px-2 py-1.5",
                                missing && "bg-warning/10 text-warning",
                                !missing && data.numeric_columns.includes(c) && "tabular-nums",
                              )}
                            >
                              {missing ? "—" : String(raw)}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="mt-3 flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={state.page === 0 || busy}
                    onClick={() => setState({ page: state.page - 1 })}
                  >
                    Previous
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={state.page + 1 >= totalPages || busy}
                    onClick={() => setState({ page: state.page + 1 })}
                  >
                    Next
                  </Button>
                  <span className="text-[11.5px] text-secondary">
                    Rows {data.offset + 1}–{Math.min(data.offset + data.rows.length, data.total)}
                  </span>
                </div>
              </>
            ) : null}
            {!error && data && !data.rows.length ? (
              <p className="py-10 text-center text-[13px] text-secondary">
                No rows match the current search.
              </p>
            ) : null}
          </SectionCard>
        </div>
      )}
    </div>
  );
}
