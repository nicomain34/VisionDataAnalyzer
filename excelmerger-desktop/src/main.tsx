import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { I18nProvider } from "@/lib/i18n";
import { AnalysisSessionProvider } from "@/lib/analysisSession";
import { addLog } from "@/lib/logStore";
import App from "./App";
import "./index.css";

addLog("INFO", "Application started.", "app");

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <I18nProvider>
      <AnalysisSessionProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </AnalysisSessionProvider>
    </I18nProvider>
  </StrictMode>,
);
