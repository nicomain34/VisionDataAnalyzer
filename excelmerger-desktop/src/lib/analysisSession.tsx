import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { engineCall, isTauri, onEngineProgress, pickFiles, pickFolder } from "@/lib/engine";
import { addLog } from "@/lib/logStore";
import type { DatasetProfile } from "@/lib/analysisTypes";

const LAST_SOURCE_KEY = "excelmerger.lastSource";

export type DatasetStatus = "idle" | "loading" | "ready" | "error";

export type DatasetSource = { folder?: string; files?: string[] };

type Progress = { done: number; total: number; file: string; phase: string };

type ModuleStore = Record<string, Record<string, unknown>>;

type SessionValue = {
  status: DatasetStatus;
  profile: DatasetProfile | null;
  source: DatasetSource | null;
  error: string;
  progress: Progress;
  sourceLabel: string;
  lastSource: DatasetSource | null;
  selectFolder: () => Promise<void>;
  selectFiles: () => Promise<void>;
  open: (source: DatasetSource) => Promise<void>;
  reload: () => Promise<void>;
  cancel: () => void;
  clear: () => void;
  /**
   * Per-module state (configuration + results) that survives navigation.
   * `initial` must be a stable module-level constant.
   */
  moduleState: <T extends Record<string, unknown>>(
    id: string,
    initial: T,
  ) => [T, (patch: Partial<T>) => void];
  capabilities: Capabilities;
};

export type Capabilities = {
  hasDataset: boolean;
  measurements: string[];
  groupings: string[];
  datetimes: string[];
  labels: string[];
  canDistribution: boolean;
  canComparison: boolean;
  canCorrelation: boolean;
  canScatter: boolean;
  canTrend: boolean;
  canLimitSupervised: boolean;
};

const EMPTY_PROGRESS: Progress = { done: 0, total: 0, file: "", phase: "" };

const SessionContext = createContext<SessionValue | null>(null);

function readLastSource(): DatasetSource | null {
  try {
    const raw = localStorage.getItem(LAST_SOURCE_KEY);
    return raw ? (JSON.parse(raw) as DatasetSource) : null;
  } catch {
    return null;
  }
}

function describe(source: DatasetSource | null): string {
  if (!source) return "";
  if (source.folder) return source.folder;
  if (source.files?.length) return `${source.files.length} selected file(s)`;
  return "";
}

export function AnalysisSessionProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<DatasetStatus>("idle");
  const [profile, setProfile] = useState<DatasetProfile | null>(null);
  const [source, setSource] = useState<DatasetSource | null>(null);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState<Progress>(EMPTY_PROGRESS);
  const [lastSource, setLastSource] = useState<DatasetSource | null>(() => readLastSource());
  const [modules, setModules] = useState<ModuleStore>({});
  const loading = useRef(false);

  useEffect(() => {
    let un: (() => void) | undefined;
    onEngineProgress((p) => {
      if (p.method !== "session_open") return;
      setProgress({
        done: p.done ?? 0,
        total: p.total ?? 0,
        file: p.file ?? "",
        phase: p.file ? "Reading data" : "Detecting schema",
      });
    })
      .then((fn) => {
        un = fn;
      })
      .catch(() => undefined);
    return () => un?.();
  }, []);

  const open = useCallback(async (next: DatasetSource) => {
    if (loading.current) return;
    if (!isTauri()) {
      setError("Dataset loading requires the desktop application.");
      setStatus("error");
      return;
    }
    loading.current = true;
    setStatus("loading");
    setError("");
    setProgress({ ...EMPTY_PROGRESS, phase: "Scanning files" });
    // A new source invalidates every result from the previous dataset.
    setModules({});
    setProfile(null);
    try {
      const res = await engineCall<DatasetProfile>("session_open", {
        folder: next.folder,
        files: next.files,
      });
      setProfile(res);
      setSource(next);
      setStatus("ready");
      setLastSource(next);
      try {
        localStorage.setItem(LAST_SOURCE_KEY, JSON.stringify(next));
      } catch {
        /* storage is optional */
      }
      addLog(
        "OK",
        `Dataset loaded: ${res.rows.toLocaleString()} rows, ${res.total_columns} columns, ` +
          `${res.valid_files}/${res.files_scanned} files${res.cached ? " (cached)" : ""}.`,
        "dataset",
      );
      if (res.failed_files > 0) {
        addLog(
          "WARN",
          `${res.failed_files} file(s) could not be processed. Analysis continued with ${res.valid_files} file(s).`,
          "dataset",
        );
      }
      for (const e of res.errors || []) addLog("ERROR", e, "dataset");
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      setError(message);
      setStatus("error");
      addLog("ERROR", message, "dataset");
    } finally {
      loading.current = false;
      setProgress(EMPTY_PROGRESS);
    }
  }, []);

  const selectFolder = useCallback(async () => {
    const folder = await pickFolder();
    if (!folder) return;
    await open({ folder });
  }, [open]);

  const selectFiles = useCallback(async () => {
    const files = await pickFiles();
    if (!files?.length) return;
    await open({ files });
  }, [open]);

  const reload = useCallback(async () => {
    const target = source || lastSource;
    if (target) await open(target);
  }, [open, source, lastSource]);

  const cancel = useCallback(() => {
    if (!loading.current) return;
    engineCall("cancel", {}).catch(() => undefined);
    addLog("WARN", "Dataset loading cancelled by the user.", "dataset");
  }, []);

  const clear = useCallback(() => {
    const key = profile?.key;
    setProfile(null);
    setSource(null);
    setModules({});
    setStatus("idle");
    setError("");
    if (key) engineCall("session_close", { key }).catch(() => undefined);
  }, [profile?.key]);

  const moduleState = useCallback(
    <T extends Record<string, unknown>>(id: string, initial: T): [T, (patch: Partial<T>) => void] => {
      const current = (modules[id] as T | undefined) ?? initial;
      const update = (patch: Partial<T>) => {
        setModules((prev) => ({
          ...prev,
          [id]: { ...(prev[id] ?? initial), ...patch },
        }));
      };
      return [current, update];
    },
    [modules],
  );

  const capabilities = useMemo<Capabilities>(() => {
    const measurements = profile?.numeric_columns ?? [];
    const groupings = profile?.grouping_columns ?? [];
    const datetimes = profile?.datetime_columns ?? [];
    const labels = profile?.label_columns ?? [];
    const ready = Boolean(profile && profile.rows > 0);
    return {
      hasDataset: Boolean(profile),
      measurements,
      groupings,
      datetimes,
      labels,
      canDistribution: ready && measurements.length > 0,
      canComparison: ready && measurements.length > 0 && groupings.length > 0,
      canCorrelation: ready && measurements.length >= 2,
      canScatter: ready && measurements.length >= 2,
      canTrend: ready && datetimes.length > 0 && measurements.length > 0,
      canLimitSupervised: ready && measurements.length > 0 && labels.length > 0,
    };
  }, [profile]);

  const value = useMemo<SessionValue>(
    () => ({
      status,
      profile,
      source,
      error,
      progress,
      sourceLabel: describe(source),
      lastSource,
      selectFolder,
      selectFiles,
      open,
      reload,
      cancel,
      clear,
      moduleState,
      capabilities,
    }),
    [
      status,
      profile,
      source,
      error,
      progress,
      lastSource,
      selectFolder,
      selectFiles,
      open,
      reload,
      cancel,
      clear,
      moduleState,
      capabilities,
    ],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside AnalysisSessionProvider");
  return ctx;
}

/** Call an analysis method against the loaded dataset. */
export function useAnalysisCall() {
  const { profile } = useSession();
  return useCallback(
    async <T,>(method: string, params: Record<string, unknown> = {}): Promise<T> => {
      if (!profile?.key) throw new Error("No dataset is loaded.");
      return engineCall<T>(method, { ...params, key: profile.key });
    },
    [profile?.key],
  );
}
