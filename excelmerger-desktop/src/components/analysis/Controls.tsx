import { Download, Info, TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { cn, formatNumber } from "@/lib/utils";

/** Short hover note for a control. Explains the parameter, not the whole page. */
export function InfoTip({ text }: { text: string }) {
  return (
    <span className="group relative inline-flex align-middle" title={text}>
      <Info className="h-3 w-3 text-secondary/70" />
      <span className="pointer-events-none absolute left-0 top-4 z-30 hidden w-60 rounded-md border border-border bg-elevated px-2 py-1.5 text-left text-[11px] font-normal leading-snug text-text shadow-lg group-hover:block">
        {text}
      </span>
    </span>
  );
}

export function Field({
  label,
  hint,
  info,
  className,
  children,
}: {
  label: string;
  hint?: string;
  info?: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <label className={cn("block text-[11px] text-secondary", className)}>
      <span className="mb-1 flex items-center gap-1">
        {label}
        {info ? <InfoTip text={info} /> : null}
      </span>
      {children}
      {hint ? <span className="mt-1 block text-[10.5px] text-secondary/80">{hint}</span> : null}
    </label>
  );
}

export function Select({
  value,
  onChange,
  options,
  disabled,
  placeholder,
  className,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  disabled?: boolean;
  placeholder?: string;
  className?: string;
}) {
  return (
    <select
      className={cn(
        "h-9 w-full rounded-lg border border-border bg-bg px-2 text-[12px] text-text disabled:opacity-50",
        className,
      )}
      value={value}
      disabled={disabled || !options.length}
      onChange={(e) => onChange(e.target.value)}
    >
      {!options.length ? <option value="">{placeholder || "No options"}</option> : null}
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

export function NumberInput({
  value,
  onChange,
  placeholder,
  step,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  step?: string;
}) {
  return (
    <input
      type="number"
      step={step}
      className="h-9 w-full rounded-lg border border-border bg-bg px-2 text-[12px] text-text"
      value={value}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}

export function Checkbox({
  checked,
  onChange,
  label,
  info,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  info?: string;
}) {
  return (
    <label className="flex items-center gap-2.5 text-[12px] text-secondary">
      <input
        type="checkbox"
        className="em-check"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className="flex items-center gap-1">
        {label}
        {info ? <InfoTip text={info} /> : null}
      </span>
    </label>
  );
}

/** Compact metric tiles — one metric is rendered exactly once. */
export function MetricGrid({
  items,
  columns = 4,
}: {
  items: { label: string; value: string | number; tone?: "default" | "success" | "warning" | "error" }[];
  columns?: 3 | 4 | 5 | 6;
}) {
  return (
    <div
      className={cn(
        "grid gap-2",
        columns === 3 && "grid-cols-2 md:grid-cols-3",
        columns === 4 && "grid-cols-2 md:grid-cols-4",
        columns === 5 && "grid-cols-2 md:grid-cols-3 xl:grid-cols-5",
        columns === 6 && "grid-cols-2 md:grid-cols-4 xl:grid-cols-6",
      )}
    >
      {items.map((it) => (
        <div
          key={it.label}
          className="rounded-lg border border-border bg-elevated/40 px-3 py-2"
        >
          <div className="text-[10.5px] uppercase tracking-wide text-secondary">{it.label}</div>
          <div
            className={cn(
              "mt-0.5 text-[15px] font-semibold tabular-nums",
              it.tone === "success" && "text-success",
              it.tone === "warning" && "text-warning",
              it.tone === "error" && "text-error",
              (!it.tone || it.tone === "default") && "text-text",
            )}
          >
            {it.value}
          </div>
        </div>
      ))}
    </div>
  );
}

export function statsItems(stats: Record<string, number | null | undefined>) {
  const order: [string, string][] = [
    ["count", "Count"],
    ["mean", "Mean"],
    ["median", "Median"],
    ["std", "Std dev"],
    ["min", "Min"],
    ["max", "Max"],
    ["p5", "P5"],
    ["p25", "P25"],
    ["p75", "P75"],
    ["p95", "P95"],
    ["iqr", "IQR"],
    ["variance", "Variance"],
    ["skew", "Skewness"],
    ["kurtosis", "Kurtosis"],
  ];
  return order
    .filter(([key]) => stats[key] !== undefined)
    .map(([key, label]) => ({
      label,
      value:
        key === "count"
          ? Number(stats[key] ?? 0).toLocaleString()
          : formatNumber(stats[key] ?? null, 4),
    }));
}

export function InsightList({ insights, warnings }: { insights?: string[]; warnings?: string[] }) {
  if (!insights?.length && !warnings?.length) return null;
  return (
    <div className="space-y-2">
      {insights?.map((line) => (
        <p key={line} className="text-[12.5px] leading-relaxed text-secondary">
          {line}
        </p>
      ))}
      {warnings?.map((line) => (
        <p
          key={line}
          className="flex items-start gap-2 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-[12px] leading-relaxed text-warning"
        >
          <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          {line}
        </p>
      ))}
    </div>
  );
}

export function ValidationNote({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-[12px] leading-relaxed text-warning">
      {children}
    </div>
  );
}

export function ExportBar({
  items,
  disabled,
}: {
  items: { label: string; onClick: () => void }[];
  disabled?: boolean;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((it) => (
        <Button key={it.label} size="sm" variant="secondary" disabled={disabled} onClick={it.onClick}>
          <Download className="h-3.5 w-3.5" />
          {it.label}
        </Button>
      ))}
    </div>
  );
}

export function SectionCard({
  title,
  subtitle,
  actions,
  children,
  bodyClassName,
}: {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
  bodyClassName?: string;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <CardTitle className="text-[14px]">{title}</CardTitle>
          {subtitle ? <p className="mt-1 text-[12px] text-secondary">{subtitle}</p> : null}
        </div>
        {actions}
      </CardHeader>
      <CardBody className={bodyClassName}>{children}</CardBody>
    </Card>
  );
}
