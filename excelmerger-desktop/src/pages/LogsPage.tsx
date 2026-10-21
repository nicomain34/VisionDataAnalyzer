import { useEffect, useState } from "react";
import { PageHeader } from "@/components/ui/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { useI18n } from "@/lib/i18n";
import { clearLogs, getLogs, subscribeLogs, type LogEntry } from "@/lib/logStore";

export function LogsPage() {
  const { t } = useI18n();
  const [logs, setLogs] = useState<LogEntry[]>(getLogs());

  useEffect(() => subscribeLogs(() => setLogs([...getLogs()])), []);

  function copyAll() {
    const text = logs
      .map((l) => `[${l.ts}] ${l.level} ${l.module}: ${l.message}`)
      .join("\n");
    navigator.clipboard?.writeText(text);
  }

  function exportLogs() {
    const text = logs
      .map((l) => `[${l.ts}] ${l.level} ${l.module}: ${l.message}`)
      .join("\n");
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "excelmerger-logs.txt";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div>
      <PageHeader
        title={t("logsTitle")}
        subtitle={t("logsSubtitle")}
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={copyAll}>
              Copy
            </Button>
            <Button variant="secondary" size="sm" onClick={exportLogs}>
              Export
            </Button>
            <Button variant="secondary" size="sm" onClick={clearLogs}>
              {t("clearLogs")}
            </Button>
          </div>
        }
      />
      <Card>
        <CardBody className="max-h-[70vh] overflow-auto font-mono text-[12px]">
          {!logs.length ? (
            <div className="text-secondary">No log entries yet.</div>
          ) : (
            logs.map((l) => (
              <div key={l.id} className="border-b border-border/40 py-1.5">
                <span className="text-secondary">[{l.ts}]</span>{" "}
                <span
                  className={
                    l.level === "ERROR"
                      ? "text-error"
                      : l.level === "WARN"
                        ? "text-warning"
                        : l.level === "OK"
                          ? "text-success"
                          : "text-secondary"
                  }
                >
                  {l.level === "WARN" ? "WARNING" : l.level}
                </span>{" "}
                <span className="text-primary">{l.module}</span>: {l.message}
              </div>
            ))
          )}
        </CardBody>
      </Card>
    </div>
  );
}
