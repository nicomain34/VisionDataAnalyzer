import { useEffect, useMemo, useRef, useState } from "react";
import { CheckCircle2, ChevronDown, Download, FolderOpen, Play } from "lucide-react";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Progress } from "@/components/ui/Progress";
import {
  AdvancedOptions,
  type ColumnFilter,
  type MergerFilters,
} from "@/components/merger/AdvancedOptions";
import { useI18n } from "@/lib/i18n";
import { addLog } from "@/lib/logStore";
import {
  engineCall,
  isTauri,
  onEngineProgress,
  pickFolder,
  pickSavePath,
} from "@/lib/engine";
import { cn } from "@/lib/utils";

type FoundFile = { path: string; name: string; size: number; selected: boolean };

const defaultFilters: MergerFilters = {
  name_contains: "",
  name_excludes: "",
  search_subfolders: true,
  skip_temp: true,
  include_hidden: false,
  remove_dupes: false,
  size_enable: false,
  size_min: "0",
  size_max: "100",
  date_preset: "any",
  date_from: "",
  date_to: "",
  sheet_contains: "",
};

export function MergerPage() {
  const { t } = useI18n();
  const [folder, setFolder] = useState("");
  const [files, setFiles] = useState<FoundFile[]>([]);
  const [types, setTypes] = useState({ csv: true, xlsx: true, xls: true, xlsm: false });
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState({ done: 0, total: 0, file: "" });
  const [status, setStatus] = useState(t("statusReady"));
  const [canSave, setCanSave] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveProgress, setSaveProgress] = useState({ done: 0, total: 0 });
  const [savedPath, setSavedPath] = useState("");
  const [summary, setSummary] = useState("");
  const [advOpen, setAdvOpen] = useState(false);
  const [filesOpen, setFilesOpen] = useState(false);
  const [filters, setFilters] = useState<MergerFilters>(defaultFilters);
  const [columnFilters, setColumnFilters] = useState<ColumnFilter[]>([
    { mode: "contains", value: "" },
  ]);
  const op = useRef(0);

  useEffect(() => {
    if (!isTauri()) return;
    const ticket = op.current;
    engineCall<{ ready: boolean; rows: number; cols: number; files: number; dupes: number }>(
      "merge_status",
    )
      .then((res) => {
        if (ticket !== op.current || !res.ready || res.rows <= 0) return;
        setCanSave(true);
        setSummary(
          `Files: ${res.files} · Rows: ${res.rows} · Columns: ${res.cols} · Duplicates removed: ${res.dupes}`,
        );
        setStatus(`Done. ${res.rows} rows ready to save.`);
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    let un: (() => void) | undefined;
    onEngineProgress((p) => {
      if (p.method === "scan_folder" || p.method === "merge") {
        setProgress({
          done: p.done ?? 0,
          total: p.total ?? 0,
          file: p.file ?? "",
        });
        if (p.method === "merge" && p.file === "Combining rows") {
          setStatus("Combining rows…");
        }
      } else if (p.method === "save_merged") {
        setSaveProgress({ done: p.done ?? 0, total: p.total ?? 0 });
      }
    })
      .then((fn) => {
        un = fn;
      })
      .catch(() => undefined);
    return () => un?.();
  }, []);

  const extensions = useMemo(() => {
    const e: string[] = [];
    if (types.csv) e.push(".csv");
    if (types.xlsx) e.push(".xlsx");
    if (types.xls) e.push(".xls");
    if (types.xlsm) e.push(".xlsm");
    return e;
  }, [types]);

  async function selectFolder() {
    try {
      const path = isTauri() ? await pickFolder() : window.prompt("Folder path");
      if (!path) return;
      setFolder(path);
      addLog("INFO", `Folder selected: ${path}`, "merger");
      await scan(path);
    } catch (e) {
      addLog("ERROR", String(e), "merger");
      setStatus(String(e));
    }
  }

  async function scan(path = folder) {
    if (!path) return;
    setBusy(true);
    setCanSave(false);
    setStatus("Scanning…");
    try {
      if (!isTauri()) {
        setFiles([]);
        setStatus("Tauri required for scan (run npm run tauri:dev)");
        addLog("WARN", "Scan skipped: not running in Tauri", "merger");
        return;
      }
      const res = await engineCall<{ files: FoundFile[]; count: number }>("scan_folder", {
        folder: path,
        extensions,
        filters,
      });
      setFiles(res.files || []);
      setStatus(`Found ${res.count ?? res.files?.length ?? 0} files.`);
      addLog("OK", `Scan finished. Found ${res.count ?? 0} file(s).`, "merger");
    } catch (e) {
      addLog("ERROR", String(e), "merger");
      setStatus(String(e));
    } finally {
      setBusy(false);
      setProgress({ done: 0, total: 0, file: "" });
    }
  }

  function applyReady(res: { rows: number; cols: number; files: number; dupes: number }) {
    setCanSave(true);
    setSummary(
      `Files: ${res.files} · Rows: ${res.rows} · Columns: ${res.cols} · Duplicates removed: ${res.dupes}`,
    );
    setStatus(`Done. ${res.rows} rows ready to save.`);
  }

  async function startMerge() {
    const selected = files.filter((f) => f.selected).map((f) => f.path);
    if (!selected.length) {
      setStatus("No files selected.");
      return;
    }
    const ticket = ++op.current;
    setBusy(true);
    setCanSave(false);
    setSavedPath("");
    setSaveProgress({ done: 0, total: 0 });
    setSummary("");
    setStatus("Merging…");
    addLog("INFO", `Merge started for ${selected.length} file(s).`, "merger");
    try {
      const res = await engineCall<{
        ok: boolean;
        rows: number;
        cols: number;
        files: number;
        dupes: number;
        errors: { file: string; error: string }[];
      }>("merge", {
        files: selected,
        remove_dupes: filters.remove_dupes,
        sheet_contains: filters.sheet_contains,
        column_filters: columnFilters.filter((c) => c.value.trim()),
      });
      if (ticket !== op.current) return;
      if (!res.ok) {
        const detail = (res.errors || [])
          .map((err) => `${err.file}: ${err.error}`)
          .filter(Boolean)
          .join(" · ");
        const msg = detail ? `Merge produced no data. ${detail}` : "Merge produced no data.";
        setStatus(msg);
        addLog("ERROR", msg, "merger");
      } else {
        setCanSave(true);
        setSummary(
          `Files: ${res.files} · Rows: ${res.rows} · Columns: ${res.cols} · Duplicates removed: ${res.dupes} · Errors: ${res.errors?.length ?? 0}`,
        );
        setStatus(`Done. ${res.rows} rows ready to save.`);
        addLog("OK", `Merge completed: ${res.rows} rows.`, "merger");
        for (const err of res.errors || []) {
          addLog("ERROR", `${err.file}: ${err.error}`, "merger");
        }
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      addLog("ERROR", msg, "merger");
      try {
        const ready = await engineCall<{
          ready: boolean;
          rows: number;
          cols: number;
          files: number;
          dupes: number;
        }>("merge_status");
        if (ticket === op.current && ready.ready && ready.rows > 0) {
          applyReady(ready);
          addLog("OK", `Merge completed: ${ready.rows} rows.`, "merger");
          return;
        }
      } catch {
        /* the engine has no table to save */
      }
      if (ticket === op.current) setStatus(msg);
    } finally {
      if (ticket === op.current) setBusy(false);
    }
  }

  async function save() {
    try {
      const path = isTauri()
        ? await pickSavePath("merged.xlsx")
        : window.prompt("Save path", "merged.xlsx");
      if (!path) return;
      setBusy(true);
      setSaving(true);
      setSavedPath("");
      setSaveProgress({ done: 0, total: 0 });
      setStatus(t("savingFile"));
      // Paint the progress bar before the save call, so the window is not blank while writing starts.
      await new Promise((resolve) => requestAnimationFrame(() => resolve(undefined)));
      const res = await engineCall<{ ok: boolean; path?: string; error?: string }>(
        "save_merged",
        { path },
      );
      if (!res.ok) throw new Error(res.error || "Save failed");
      setSavedPath(res.path || path);
      setStatus(t("savedReady"));
      addLog("OK", `File saved: ${res.path}`, "merger");
    } catch (e) {
      addLog("ERROR", String(e), "merger");
      setStatus(String(e));
      setSaveProgress({ done: 0, total: 0 });
    } finally {
      setBusy(false);
      setSaving(false);
    }
  }

  const typeOptions = [
    ["csv", "CSV (.csv)"],
    ["xlsx", "Excel (.xlsx)"],
    ["xls", "Excel old (.xls)"],
    ["xlsm", "Excel macros (.xlsm)"],
  ] as const;

  return (
    <div>
      <PageHeader title={t("mergerTitle")} subtitle={t("mergerSubtitle")} />

      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>{t("stepFolder")}</CardTitle>
          </CardHeader>
          <CardBody>
            <div className="flex items-center gap-5 rounded-xl border border-dashed border-border bg-elevated/40 px-5 py-5">
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-bg/60 text-secondary">
                <FolderOpen className="h-7 w-7" strokeWidth={1.5} />
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-[14px] font-semibold text-text">
                  {t("selectFolderPrompt")}
                </div>
                <div className="mt-1 text-[12px] leading-relaxed text-secondary">
                  {t("selectFolderHelp")}
                </div>
              </div>
              <Button onClick={selectFolder} disabled={busy} className="shrink-0">
                <FolderOpen className="h-4 w-4" />
                {folder ? t("changeFolder") : t("selectFolder")}
              </Button>
            </div>

            <div className="mt-3 text-[12px] text-secondary">
              {folder
                ? `${folder}${files.length ? ` · ${t("filesFound", { count: files.length })}` : ""}`
                : t("noFolder")}
            </div>

            {files.length > 0 ? (
              <div className="mt-4">
                <button
                  type="button"
                  className="flex w-full items-center justify-between rounded-lg border border-border bg-elevated/50 px-3 py-2 text-left text-[13px]"
                  onClick={() => setFilesOpen((v) => !v)}
                >
                  <span className="font-medium">
                    {t("filesFound", { count: files.length })}
                  </span>
                  <ChevronDown
                    className={cn(
                      "h-4 w-4 text-secondary transition",
                      filesOpen ? "rotate-180" : "",
                    )}
                  />
                </button>
                {filesOpen ? (
                  <div className="mt-2">
                    <div className="mb-2 flex gap-2">
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() =>
                          setFiles((fs) => fs.map((f) => ({ ...f, selected: true })))
                        }
                      >
                        {t("selectAll")}
                      </Button>
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() =>
                          setFiles((fs) => fs.map((f) => ({ ...f, selected: false })))
                        }
                      >
                        {t("deselectAll")}
                      </Button>
                    </div>
                    <div className="max-h-48 overflow-auto rounded-xl border border-border">
                      <table className="w-full text-left text-[12px]">
                        <thead className="sticky top-0 bg-elevated text-secondary">
                          <tr>
                            <th className="px-3 py-2">✓</th>
                            <th className="px-3 py-2">File</th>
                            <th className="px-3 py-2">Path</th>
                          </tr>
                        </thead>
                        <tbody>
                          {files.map((f) => (
                            <tr key={f.path} className="border-t border-border/70">
                              <td className="px-3 py-1.5">
                                <input
                                  type="checkbox"
                                  className="em-check"
                                  checked={f.selected}
                                  onChange={() =>
                                    setFiles((all) =>
                                      all.map((x) =>
                                        x.path === f.path
                                          ? { ...x, selected: !x.selected }
                                          : x,
                                      ),
                                    )
                                  }
                                />
                              </td>
                              <td className="px-3 py-1.5">{f.name}</td>
                              <td className="truncate px-3 py-1.5 text-secondary">
                                {f.path}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t("stepTypes")}</CardTitle>
          </CardHeader>
          <CardBody className="flex flex-wrap gap-3">
            {typeOptions.map(([k, label]) => {
              const checked = types[k];
              return (
                <label
                  key={k}
                  className={cn(
                    "flex cursor-pointer items-center gap-2.5 rounded-lg border px-3.5 py-2.5 text-[13px] transition",
                    checked
                      ? "border-primary/40 bg-primary/10 text-text"
                      : "border-border bg-elevated text-secondary hover:text-text",
                  )}
                >
                  <input
                    type="checkbox"
                    className="em-check"
                    checked={checked}
                    onChange={(e) =>
                      setTypes((t0) => ({ ...t0, [k]: e.target.checked }))
                    }
                  />
                  {label}
                </label>
              );
            })}
          </CardBody>
        </Card>

        <AdvancedOptions
          open={advOpen}
          onToggle={() => setAdvOpen((v) => !v)}
          filters={filters}
          setFilters={setFilters}
          columnFilters={columnFilters}
          setColumnFilters={setColumnFilters}
          busy={busy}
          canApply={Boolean(folder)}
          onApply={() => scan()}
        />

        <Card>
          <CardHeader>
            <CardTitle>{t("stepMerge")}</CardTitle>
          </CardHeader>
          <CardBody className="space-y-4">
            <Button
              size="lg"
              onClick={startMerge}
              disabled={busy || !files.length}
              className="min-w-[180px]"
            >
              <Play className="h-4 w-4 fill-current" />
              {t("startMerge")}
            </Button>
            <Progress value={progress.done} max={progress.total || 1} />
            <div className="flex items-start gap-2 text-[13px] text-secondary">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
              <div>
                <div>
                  {status}
                  {progress.file ? ` · ${progress.file}` : ""}
                </div>
                {summary ? (
                  <div className="mt-1 text-[12px] text-success">{summary}</div>
                ) : null}
              </div>
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t("stepSave")}</CardTitle>
          </CardHeader>
          <CardBody className="space-y-3">
            <div className="flex flex-wrap items-center gap-4">
              <Button
                variant="secondary"
                disabled={!canSave || busy}
                onClick={save}
                className="min-w-[200px]"
              >
                <Download className="h-4 w-4" />
                {saving ? t("savingFile") : t("saveMerged")}
              </Button>
              {!canSave ? (
                <span className="text-[12px] text-secondary">{t("saveHint")}</span>
              ) : null}
            </div>
            {saving || savedPath ? (
              <div className="space-y-2">
                <Progress value={saving ? saveProgress.done : saveProgress.total || 1} max={saveProgress.total || 1} />
                <div className={cn("text-[12px]", savedPath ? "text-success" : "text-warning")}>
                  {savedPath
                    ? `${t("savedReady")} ${savedPath}`
                    : saveProgress.total
                      ? t("savingProgress", {
                          done: saveProgress.done.toLocaleString(),
                          total: saveProgress.total.toLocaleString(),
                        })
                      : t("savingFile")}
                </div>
              </div>
            ) : null}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
