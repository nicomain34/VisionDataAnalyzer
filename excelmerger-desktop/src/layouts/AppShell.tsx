import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  BarChart3,
  ChevronDown,
  FileSpreadsheet,
  FileText,
  GitCompare,
  LayoutDashboard,
  Layers,
  Network,
  ScatterChart,
  ScrollText,
  Settings,
  SlidersHorizontal,
  Table2,
  TriangleAlert,
  TrendingUp,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";
import { LgLogo } from "@/components/brand/LgLogo";

const analysisLinks = [
  { to: "/analysis/overview", key: "navOverview" as const, icon: LayoutDashboard },
  { to: "/analysis/distribution", key: "navDistribution" as const, icon: BarChart3 },
  { to: "/analysis/comparison", key: "navComparison" as const, icon: GitCompare },
  { to: "/analysis/data-quality", key: "navDataQuality" as const, icon: TriangleAlert },
  { to: "/analysis/correlation", key: "navCorrelation" as const, icon: Network },
  { to: "/analysis/scatter", key: "navScatter" as const, icon: ScatterChart },
  { to: "/analysis/trend", key: "navTrend" as const, icon: TrendingUp },
  { to: "/analysis/batch", key: "navBatch" as const, icon: Layers },
  { to: "/analysis/limit", key: "navLimit" as const, icon: SlidersHorizontal },
  { to: "/analysis/data-table", key: "navDataTable" as const, icon: Table2 },
  { to: "/analysis/outliers", key: "navOutliers" as const, icon: TriangleAlert },
  { to: "/analysis/reports", key: "navReports" as const, icon: FileText },
];

export function AppShell() {
  const { t } = useI18n();
  const location = useLocation();
  const onAnalysis = location.pathname.startsWith("/analysis");
  const [analysisOpen, setAnalysisOpen] = useState(onAnalysis);

  useEffect(() => {
    if (onAnalysis) setAnalysisOpen(true);
  }, [onAnalysis]);

  return (
    <div className="flex h-full min-h-0 bg-bg">
      <aside className="flex w-[240px] shrink-0 flex-col border-r border-border bg-sidebar">
        <div className="flex items-center gap-2.5 px-4 pb-7 pt-6">
          <LgLogo className="h-8 w-8 shrink-0" />
          <div className="text-[13px] font-semibold leading-tight tracking-tight text-text">
            {t("brand")}
          </div>
        </div>

        <nav className="flex flex-1 flex-col px-3">
          <div className="space-y-1">
            <NavItem to="/" end icon={FileSpreadsheet} label={t("navMerger")} />

            <button
              type="button"
              onClick={() => setAnalysisOpen((v) => !v)}
              className={cn(
                "flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-[13px] font-medium transition",
                onAnalysis
                  ? "text-text"
                  : "text-secondary hover:bg-elevated hover:text-text",
              )}
            >
              <BarChart3
                className={cn("h-4 w-4", onAnalysis ? "text-primary" : "text-secondary")}
              />
              <span className="flex-1 text-left">{t("navAnalysis")}</span>
              <ChevronDown
                className={cn(
                  "h-3.5 w-3.5 text-secondary transition",
                  analysisOpen ? "rotate-180" : "",
                )}
              />
            </button>

            {analysisOpen ? (
              <div className="ml-2 space-y-0.5 border-l border-border/70 pl-2">
                {analysisLinks.map((l) => (
                  <NavItem
                    key={l.to}
                    to={l.to}
                    icon={l.icon}
                    label={t(l.key)}
                    nested
                  />
                ))}
              </div>
            ) : null}
          </div>

          <div className="mt-auto space-y-1 pb-4 pt-6">
            <NavItem to="/logs" icon={ScrollText} label={t("navLogs")} />
            <NavItem to="/settings" icon={Settings} label={t("navSettings")} />
          </div>
        </nav>
      </aside>

      <main className="min-w-0 flex-1 overflow-auto">
        <div className="mx-auto max-w-[1440px] px-7 py-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

function NavItem({
  to,
  icon: Icon,
  label,
  end,
  nested,
}: {
  to: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  end?: boolean;
  nested?: boolean;
}) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-[13px] font-medium transition",
          nested && "py-2 text-[12.5px]",
          isActive
            ? "bg-primary text-white shadow-sm shadow-primary/25"
            : "text-secondary hover:bg-elevated hover:text-text",
        )
      }
    >
      {({ isActive }) => (
        <>
          <Icon
            className={cn(
              "h-4 w-4",
              isActive ? "text-white" : "text-secondary",
            )}
          />
          <span>{label}</span>
        </>
      )}
    </NavLink>
  );
}
