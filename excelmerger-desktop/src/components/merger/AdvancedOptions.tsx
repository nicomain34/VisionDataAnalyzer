import { useState } from "react";
import {
  Calendar,
  ChevronDown,
  FileText,
  Filter,
  Info,
  Plus,
  Settings2,
  SlidersHorizontal,
  Table2,
  X,
} from "lucide-react";
import { Card, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export type MergerFilters = {
  name_contains: string;
  name_excludes: string;
  search_subfolders: boolean;
  skip_temp: boolean;
  include_hidden: boolean;
  remove_dupes: boolean;
  size_enable: boolean;
  size_min: string;
  size_max: string;
  date_preset: string;
  date_from: string;
  date_to: string;
  sheet_contains: string;
};

export type ColumnFilter = { mode: string; value: string };

type Props = {
  open: boolean;
  onToggle: () => void;
  filters: MergerFilters;
  setFilters: React.Dispatch<React.SetStateAction<MergerFilters>>;
  columnFilters: ColumnFilter[];
  setColumnFilters: React.Dispatch<React.SetStateAction<ColumnFilter[]>>;
  busy: boolean;
  canApply: boolean;
  onApply: () => void;
};

export function AdvancedOptions({
  open,
  onToggle,
  filters,
  setFilters,
  columnFilters,
  setColumnFilters,
  busy,
  canApply,
  onApply,
}: Props) {
  const { t } = useI18n();

  return (
    <Card className="overflow-hidden border-primary/25">
      <button
        type="button"
        className="flex w-full items-center justify-between px-5 py-4 text-left transition hover:bg-elevated/40"
        onClick={onToggle}
      >
        <span className="flex items-center gap-2.5 text-[15px] font-semibold">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/15 text-primary">
            <SlidersHorizontal className="h-4 w-4" />
          </span>
          {t("stepAdvanced")}
        </span>
        <ChevronDown
          className={cn(
            "h-4 w-4 text-secondary transition",
            open ? "rotate-180" : "",
          )}
        />
      </button>

      {open ? (
        <CardBody className="space-y-4 border-t border-border pt-4">
          <div className="grid gap-4 lg:grid-cols-2">
            {/* Left column */}
            <div className="space-y-3">
              <Section title={t("fileFilters")} icon={Filter}>
                <Field
                  label={t("nameContains")}
                  hint={t("nameContainsHint")}
                  placeholder={t("nameContainsPh")}
                  value={filters.name_contains}
                  onChange={(v) => setFilters((f) => ({ ...f, name_contains: v }))}
                />
                <Field
                  label={t("nameExcludes")}
                  hint={t("nameExcludesHint")}
                  placeholder={t("nameExcludesPh")}
                  value={filters.name_excludes}
                  onChange={(v) => setFilters((f) => ({ ...f, name_excludes: v }))}
                />
              </Section>

              <Section title={t("dateFilters")} icon={Calendar}>
                <label className="block text-[12px] text-secondary">
                  {t("datePreset")}
                  <select
                    className="mt-1 h-10 w-full rounded-lg border border-border bg-bg px-3 text-[13px] text-text"
                    value={filters.date_preset}
                    onChange={(e) =>
                      setFilters((f) => ({ ...f, date_preset: e.target.value }))
                    }
                  >
                    <option value="any">{t("dateAny")}</option>
                    <option value="24h">{t("date24h")}</option>
                    <option value="7d">{t("date7d")}</option>
                    <option value="30d">{t("date30d")}</option>
                    <option value="custom">{t("dateCustom")}</option>
                  </select>
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <Field
                    label={t("dateFrom")}
                    placeholder="DD.MM.YYYY"
                    value={filters.date_from}
                    onChange={(v) => setFilters((f) => ({ ...f, date_from: v }))}
                    disabled={filters.date_preset !== "custom" && filters.date_preset !== "any"}
                  />
                  <Field
                    label={t("dateTo")}
                    placeholder="DD.MM.YYYY"
                    value={filters.date_to}
                    onChange={(v) => setFilters((f) => ({ ...f, date_to: v }))}
                    disabled={filters.date_preset !== "custom" && filters.date_preset !== "any"}
                  />
                </div>
              </Section>

              <Section title={t("sizeFilters")} icon={FileText}>
                <CheckRow
                  label={t("sizeEnable")}
                  checked={filters.size_enable}
                  onChange={(v) => setFilters((f) => ({ ...f, size_enable: v }))}
                />
                <div className="grid grid-cols-2 gap-2">
                  <Field
                    label={t("sizeMin")}
                    value={filters.size_min}
                    onChange={(v) => setFilters((f) => ({ ...f, size_min: v }))}
                    disabled={!filters.size_enable}
                  />
                  <Field
                    label={t("sizeMax")}
                    value={filters.size_max}
                    onChange={(v) => setFilters((f) => ({ ...f, size_max: v }))}
                    disabled={!filters.size_enable}
                  />
                </div>
              </Section>
            </div>

            {/* Right column */}
            <div className="space-y-3">
              <Section title={t("dataFilters")} icon={Table2}>
                <Field
                  label={t("sheetContains")}
                  hint={t("sheetContainsHint")}
                  placeholder={t("sheetContainsPh")}
                  value={filters.sheet_contains}
                  onChange={(v) => setFilters((f) => ({ ...f, sheet_contains: v }))}
                />
                <div className="text-[12px] text-secondary">{t("colFilter")}</div>
                <div className="space-y-2">
                  {columnFilters.map((cf, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <select
                        className="h-9 rounded-lg border border-border bg-bg px-2 text-[12px]"
                        value={cf.mode}
                        onChange={(e) =>
                          setColumnFilters((rows) =>
                            rows.map((r, j) =>
                              j === i ? { ...r, mode: e.target.value } : r,
                            ),
                          )
                        }
                      >
                        <option value="contains">contains</option>
                        <option value="equals">equals</option>
                        <option value="not_contains">not_contains</option>
                      </select>
                      <input
                        className="h-9 flex-1 rounded-lg border border-border bg-bg px-3 text-[12px] text-text outline-none focus:border-primary"
                        value={cf.value}
                        placeholder={t("colFilterPh")}
                        onChange={(e) =>
                          setColumnFilters((rows) =>
                            rows.map((r, j) =>
                              j === i ? { ...r, value: e.target.value } : r,
                            ),
                          )
                        }
                      />
                      <button
                        type="button"
                        className="rounded-md p-1.5 text-secondary hover:bg-elevated hover:text-text"
                        onClick={() =>
                          setColumnFilters((rows) => rows.filter((_, j) => j !== i))
                        }
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
                <Button
                  size="sm"
                  variant="secondary"
                  className="mt-1"
                  onClick={() =>
                    setColumnFilters((rows) => [...rows, { mode: "contains", value: "" }])
                  }
                >
                  <Plus className="h-3.5 w-3.5" />
                  {t("addColFilter")}
                </Button>
              </Section>

              <Section title={t("otherOptions")} icon={Settings2}>
                <CheckRow
                  label={t("includeHidden")}
                  checked={filters.include_hidden}
                  onChange={(v) => setFilters((f) => ({ ...f, include_hidden: v }))}
                />
                <CheckRow
                  label={t("searchSubfolders")}
                  checked={filters.search_subfolders}
                  onChange={(v) => setFilters((f) => ({ ...f, search_subfolders: v }))}
                />
                <CheckRow
                  label={t("skipTemp")}
                  checked={filters.skip_temp}
                  onChange={(v) => setFilters((f) => ({ ...f, skip_temp: v }))}
                />
                <CheckRow
                  label={t("removeDupes")}
                  checked={filters.remove_dupes}
                  onChange={(v) => setFilters((f) => ({ ...f, remove_dupes: v }))}
                />
              </Section>
            </div>
          </div>

          <div className="flex justify-end">
            <Button disabled={busy || !canApply} onClick={onApply}>
              {t("applyFilters")}
            </Button>
          </div>
        </CardBody>
      ) : null}
    </Card>
  );
}

function Section({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-border bg-elevated/40 p-3.5">
      <div className="mb-3 flex items-center gap-2 text-[13px] font-semibold text-text">
        <Icon className="h-3.5 w-3.5 text-primary" />
        {title}
      </div>
      <div className="space-y-2.5">{children}</div>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  hint,
  disabled,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  hint?: string;
  disabled?: boolean;
}) {
  const [showHint, setShowHint] = useState(false);
  return (
    <label className={cn("block text-[12px] text-secondary", disabled && "opacity-40")}>
      <span className="mb-1 flex items-center gap-1.5">
        {label}
        {hint ? (
          <button
            type="button"
            className="relative text-secondary/80 hover:text-primary"
            onMouseEnter={() => setShowHint(true)}
            onMouseLeave={() => setShowHint(false)}
            onClick={(e) => {
              e.preventDefault();
              setShowHint((v) => !v);
            }}
          >
            <Info className="h-3 w-3" />
            {showHint ? (
              <span className="absolute left-0 top-5 z-20 w-56 rounded-lg border border-border bg-card px-2.5 py-2 text-[11px] leading-snug text-secondary shadow-lg">
                {hint}
              </span>
            ) : null}
          </button>
        ) : null}
      </span>
      <input
        className="mt-0.5 h-10 w-full rounded-lg border border-border bg-bg px-3 text-[13px] text-text outline-none focus:border-primary disabled:cursor-not-allowed"
        value={value}
        placeholder={placeholder}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}

function CheckRow({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-2.5 text-[13px] text-text">
      <input
        type="checkbox"
        className="em-check"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      {label}
    </label>
  );
}
