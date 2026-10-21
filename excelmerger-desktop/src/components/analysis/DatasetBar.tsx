import { FolderOpen, Files, RefreshCw, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { Progress } from "@/components/ui/Progress";
import { Badge } from "@/components/ui/Badge";
import { useI18n } from "@/lib/i18n";
import { useSession } from "@/lib/analysisSession";

/** Dataset selector shared by every analysis page; the dataset is loaded once. */
export function DatasetBar() {
  const { t } = useI18n();
  const {
    status,
    profile,
    sourceLabel,
    lastSource,
    progress,
    error,
    selectFolder,
    selectFiles,
    open,
    reload,
    cancel,
    clear,
  } = useSession();

  const busy = status === "loading";

  return (
    <Card className="mb-4">
      <CardBody className="flex flex-wrap items-center gap-x-4 gap-y-3 py-3">
        <div className="min-w-0 flex-1">
          {profile ? (
            <>
              <div className="flex items-center gap-2">
                <span className="truncate text-[13px] font-medium text-text">
                  {sourceLabel || profile.source_folder || "Dataset"}
                </span>
                <Badge tone={profile.failed_files ? "warning" : "success"}>
                  {profile.valid_files}/{profile.files_scanned} files
                </Badge>
                {profile.truncated ? <Badge tone="warning">row limit reached</Badge> : null}
              </div>
              <div className="mt-1 text-[11.5px] text-secondary">
                {profile.rows.toLocaleString()} rows · {profile.total_columns} columns ·{" "}
                {profile.numeric_columns.length} numeric · {profile.grouping_columns.length} grouping
                {profile.datetime_columns.length ? ` · ${profile.datetime_columns.length} date/time` : ""}
                {profile.total_size ? ` · ${profile.total_size}` : ""}
              </div>
            </>
          ) : busy ? (
            <LoadProgress progress={progress} />
          ) : (
            <>
              <div className="text-[13px] font-medium text-text">No dataset loaded</div>
              <div className="mt-1 text-[11.5px] text-secondary">
                {error
                  ? error
                  : "Select a folder or files once — every analysis module reuses the same dataset."}
              </div>
            </>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {busy ? (
            <Button size="sm" variant="secondary" onClick={cancel}>
              <X className="h-4 w-4" />
              Cancel
            </Button>
          ) : null}
          <Button size="sm" onClick={selectFolder} disabled={busy}>
            <FolderOpen className="h-4 w-4" />
            {t("selectFolder")}
          </Button>
          <Button size="sm" variant="secondary" onClick={selectFiles} disabled={busy}>
            <Files className="h-4 w-4" />
            {t("selectFiles")}
          </Button>
          {profile ? (
            <>
              <Button
                size="sm"
                variant="secondary"
                onClick={reload}
                disabled={busy}
                title="Re-read the source files"
              >
                <RefreshCw className="h-4 w-4" />
              </Button>
              <Button size="sm" variant="ghost" onClick={clear} disabled={busy} title="Close dataset">
                <X className="h-4 w-4" />
              </Button>
            </>
          ) : lastSource && !busy ? (
            <Button size="sm" variant="secondary" onClick={() => open(lastSource)}>
              <RefreshCw className="h-4 w-4" />
              Reload last dataset
            </Button>
          ) : null}
        </div>
      </CardBody>
    </Card>
  );
}

function LoadProgress({
  progress,
  wide,
}: {
  progress: { done: number; total: number; file: string; phase: string };
  wide?: boolean;
}) {
  const known = progress.total > 0;
  const pct = known ? Math.min(100, Math.round((progress.done / progress.total) * 100)) : 0;
  return (
    <div className={wide ? "mx-auto w-full max-w-lg text-left" : "w-full"}>
      <div className="flex items-baseline justify-between gap-3 text-[13px] font-medium text-text">
        <span>{progress.phase || "Loading dataset"}</span>
        <span className="tabular-nums text-secondary">
          {known ? `${progress.done}/${progress.total} · ${pct}%` : "…"}
        </span>
      </div>
      <div className="mt-2">
        <Progress
          value={progress.done}
          max={progress.total || 1}
          indeterminate={!known || progress.done === 0}
        />
      </div>
      <div className="mt-1.5 truncate text-[11.5px] text-secondary">
        {progress.file || (known ? "Reading files" : "Preparing the file list")}
      </div>
    </div>
  );
}

/** Large progress card used while a dataset is being read into a tool. */
export function DatasetLoadingCard() {
  const { progress } = useSession();
  return (
    <Card>
      <CardBody className="py-10">
        <LoadProgress progress={progress} wide />
      </CardBody>
    </Card>
  );
}

/** Blocks a module until the dataset supports it, with an explicit reason. */
export function AnalysisGate({
  ready,
  requirement,
  children,
}: {
  ready: boolean;
  requirement: string;
  children: React.ReactNode;
}) {
  const { profile, status } = useSession();
  if (status === "loading") {
    return <DatasetLoadingCard />;
  }
  if (!profile) {
    return (
      <Card>
        <CardBody className="py-14 text-center text-[13px] text-secondary">
          Select a folder or files to start the analysis session.
        </CardBody>
      </Card>
    );
  }
  if (!ready) {
    return (
      <Card>
        <CardBody className="py-14 text-center text-[13px] text-secondary">{requirement}</CardBody>
      </Card>
    );
  }
  return <>{children}</>;
}
