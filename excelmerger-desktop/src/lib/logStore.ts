import type { LogLevel } from "./engine";

export type LogEntry = {
  id: number;
  ts: string;
  level: LogLevel;
  module: string;
  message: string;
};

let seq = 1;
const listeners = new Set<() => void>();
let entries: LogEntry[] = [];

function notify() {
  listeners.forEach((l) => l());
}

export function addLog(level: LogLevel, message: string, module = "app") {
  entries = [
    ...entries,
    {
      id: seq++,
      ts: new Date().toISOString().replace("T", " ").slice(0, 19),
      level,
      module,
      message,
    },
  ].slice(-2000);
  listeners.forEach((l) => l());
}

export function clearLogs() {
  entries = [];
  notify();
  addLog("INFO", "Log cleared.", "logs");
}

export function getLogs() {
  return entries;
}

export function subscribeLogs(cb: () => void) {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}
