import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/layouts/AppShell";
import { MergerPage } from "@/pages/merger/MergerPage";
import { OverviewPage } from "@/pages/analysis/OverviewPage";
import { DistributionPage } from "@/pages/analysis/DistributionPage";
import { ComparisonPage } from "@/pages/analysis/ComparisonPage";
import { OutliersPage } from "@/pages/analysis/OutliersPage";
import { DataTablePage } from "@/pages/analysis/DataTablePage";
import { DataQualityPage } from "@/pages/analysis/DataQualityPage";
import { CorrelationPage } from "@/pages/analysis/CorrelationPage";
import { ScatterPage } from "@/pages/analysis/ScatterPage";
import { TimeTrendPage } from "@/pages/analysis/TimeTrendPage";
import { BatchComparisonPage } from "@/pages/analysis/BatchComparisonPage";
import { LimitFinderPage } from "@/pages/analysis/LimitFinderPage";
import { ReportsPage } from "@/pages/analysis/ReportsPage";
import { LogsPage } from "@/pages/LogsPage";
import { SettingsPage } from "@/pages/SettingsPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<MergerPage />} />
        <Route path="analysis/overview" element={<OverviewPage />} />
        <Route path="analysis/distribution" element={<DistributionPage />} />
        <Route path="analysis/comparison" element={<ComparisonPage />} />
        <Route path="analysis/outliers" element={<OutliersPage />} />
        <Route path="analysis/data-table" element={<DataTablePage />} />
        <Route path="analysis/data-quality" element={<DataQualityPage />} />
        <Route path="analysis/correlation" element={<CorrelationPage />} />
        <Route path="analysis/scatter" element={<ScatterPage />} />
        <Route path="analysis/trend" element={<TimeTrendPage />} />
        <Route path="analysis/batch" element={<BatchComparisonPage />} />
        <Route path="analysis/limit" element={<LimitFinderPage />} />
        <Route path="analysis/reports" element={<ReportsPage />} />
        <Route path="logs" element={<LogsPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
