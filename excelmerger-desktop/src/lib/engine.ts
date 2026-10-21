import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";

export type ProgressEvent = {
  method: string;
  done?: number;
  total?: number;
  values?: number;
  file?: string;
};

export type LogLevel = "INFO" | "WARN" | "ERROR" | "OK";

type EngineResponse<T> = { id: number; result?: T; error?: string };

let reqId = 1;

export async function engineCall<T = unknown>(
  method: string,
  params: Record<string, unknown> = {},
): Promise<T> {
  const id = reqId++;
  const raw = await invoke<EngineResponse<T>>("engine_request", {
    method,
    params,
    id,
  });
  if (raw.error) throw new Error(raw.error);
  return raw.result as T;
}

export async function onEngineProgress(
  cb: (p: ProgressEvent) => void,
): Promise<UnlistenFn> {
  return listen<ProgressEvent>("engine-progress", (e) => cb(e.payload));
}

export async function pickFolder(): Promise<string | null> {
  return invoke<string | null>("pick_folder");
}

export async function pickFiles(): Promise<string[]> {
  return invoke<string[]>("pick_files");
}

export async function pickSavePath(
  defaultName = "merged.xlsx",
): Promise<string | null> {
  return invoke<string | null>("pick_save", { defaultName });
}

/** Browser/dev fallback when not running inside Tauri */
export function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}
