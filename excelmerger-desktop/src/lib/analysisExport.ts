import { useCallback } from "react";
import { pickSavePath } from "@/lib/engine";
import { addLog } from "@/lib/logStore";
import { useAnalysisCall } from "@/lib/analysisSession";

type ExportResponse = { ok: boolean; path?: string; rows?: number; error?: string; sections?: number };

/** Export helpers shared by every analysis module. */
export function useExport(module: string) {
  const call = useAnalysisCall();

  const exportKind = useCallback(
    async (kind: string, defaultName: string) => {
      const path = await pickSavePath(defaultName);
      if (!path) return;
      try {
        const res = await call<ExportResponse>("session_export", { kind, path });
        if (!res.ok) addLog("ERROR", res.error || "Export failed.", module);
        else addLog("OK", `Exported ${res.rows ?? 0} row(s) to ${res.path}`, module);
      } catch (e) {
        addLog("ERROR", e instanceof Error ? e.message : String(e), module);
      }
    },
    [call, module],
  );

  const exportReport = useCallback(
    async (format: "xlsx" | "html", sections?: string[]) => {
      const path = await pickSavePath(
        format === "html" ? "analysis-report.html" : "analysis-report.xlsx",
      );
      if (!path) return;
      try {
        const res = await call<ExportResponse>("session_report", { path, format, sections });
        if (!res.ok) addLog("ERROR", res.error || "Report export failed.", module);
        else addLog("OK", `Report with ${res.sections ?? 0} table(s): ${res.path}`, module);
      } catch (e) {
        addLog("ERROR", e instanceof Error ? e.message : String(e), module);
      }
    },
    [call, module],
  );

  return { exportKind, exportReport };
}
