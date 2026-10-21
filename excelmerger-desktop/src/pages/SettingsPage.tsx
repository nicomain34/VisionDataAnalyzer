import { Link } from "react-router-dom";
import { List } from "lucide-react";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { useI18n } from "@/lib/i18n";

export function SettingsPage() {
  const { t, lang, setLang } = useI18n();
  return (
    <div>
      <PageHeader title={t("settingsTitle")} subtitle={t("settingsSubtitle")} />
      <div className="grid max-w-3xl gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>{t("language")}</CardTitle>
          </CardHeader>
          <CardBody>
            <select
              className="h-10 w-full rounded-lg border border-border bg-elevated px-3 text-[13px] text-text"
              value={lang}
              onChange={(e) => setLang(e.target.value as "en" | "pl")}
            >
              <option value="en">English</option>
              <option value="pl">Polski</option>
            </select>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t("navLogs")}</CardTitle>
          </CardHeader>
          <CardBody className="space-y-3 text-[13px] text-secondary">
            <p>{t("logsSubtitle")}</p>
            <Link
              to="/logs"
              className="inline-flex h-9 items-center gap-2 rounded-lg border border-border bg-elevated px-3 text-[13px] font-semibold text-text hover:bg-border/40"
            >
              <List className="h-4 w-4" />
              {t("openLogs")}
            </Link>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
