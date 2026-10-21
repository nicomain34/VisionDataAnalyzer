import { ChevronDown, Globe } from "lucide-react";
import { useI18n } from "@/lib/i18n";

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}) {
  const { lang, setLang } = useI18n();
  return (
    <div className="mb-6 flex items-start justify-between gap-4">
      <div>
        <h1 className="text-[28px] font-bold tracking-tight text-text">{title}</h1>
        {subtitle ? (
          <p className="mt-1.5 text-[13px] text-secondary">{subtitle}</p>
        ) : null}
      </div>
      <div className="flex items-center gap-3">
        {actions}
        <label className="relative inline-flex h-9 cursor-pointer items-center gap-2 rounded-lg border border-border bg-elevated px-3 text-[13px] text-text">
          <Globe className="h-3.5 w-3.5 text-secondary" />
          <span>{lang === "en" ? "English" : "Polski"}</span>
          <ChevronDown className="h-3.5 w-3.5 text-secondary" />
          <select
            className="absolute inset-0 cursor-pointer opacity-0"
            value={lang}
            onChange={(e) => setLang(e.target.value as "en" | "pl")}
            aria-label="Language"
          >
            <option value="en">English</option>
            <option value="pl">Polski</option>
          </select>
        </label>
      </div>
    </div>
  );
}
