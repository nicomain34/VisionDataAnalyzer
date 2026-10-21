import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody } from "@/components/ui/Card";
import { useI18n } from "@/lib/i18n";

export function PlaceholderPage({
  titleKey,
  subtitleKey,
}: {
  titleKey: "navDataTable" | "navComparison" | "navOutliers" | "navDataQuality" | "navSettings";
  subtitleKey?: "settingsSubtitle" | "emptyAnalysis";
}) {
  const { t } = useI18n();
  return (
    <div>
      <PageHeader title={t(titleKey)} subtitle={subtitleKey ? t(subtitleKey) : undefined} />
      <Card>
        <CardBody className="py-16 text-center text-secondary">{t("comingSoon")}</CardBody>
      </Card>
    </div>
  );
}
