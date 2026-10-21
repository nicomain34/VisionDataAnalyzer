import { useState } from "react";
import { Save, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { SectionCard, Select, ValidationNote } from "@/components/analysis/Controls";
import { useI18n } from "@/lib/i18n";
import { useSession } from "@/lib/analysisSession";
import { addLog } from "@/lib/logStore";
import {
  deletePreset,
  loadPresets,
  missingColumns,
  savePreset,
} from "@/lib/analysisPresets";
import type { AnalysisPreset } from "@/lib/analysisTypes";

/** Save/load an analysis configuration; dataset rows are never stored. */
export function PresetBar({
  type,
  config,
  requiredColumns,
  onLoad,
}: {
  type: string;
  config: Record<string, unknown>;
  requiredColumns: (string | undefined)[];
  onLoad: (config: Record<string, unknown>) => void;
}) {
  const { t } = useI18n();
  const { profile } = useSession();
  const [presets, setPresets] = useState<AnalysisPreset[]>(() => loadPresets(type));
  const [name, setName] = useState("");
  const [selected, setSelected] = useState("");
  const [warning, setWarning] = useState("");

  const available = profile?.columns.map((c) => c.name) ?? [];

  function save() {
    const label = name.trim() || `${type} ${new Date().toLocaleDateString()}`;
    setPresets(savePreset({ name: label, type, savedAt: "", config }));
    setName(label);
    setSelected(label);
    addLog("OK", `Saved analysis preset "${label}".`, type);
  }

  function load(presetName: string) {
    setSelected(presetName);
    const preset = presets.find((p) => p.name === presetName);
    if (!preset) return;
    const cfg = preset.config || {};
    const needed = requiredColumns.map((key) =>
      typeof key === "string" ? (cfg[key] as string | undefined) : undefined,
    );
    const missing = missingColumns(needed, available);
    if (missing.length) {
      setWarning(
        `Preset "${presetName}" refers to column(s) not present in the current dataset: ${missing.join(", ")}. ` +
          "The remaining settings were applied.",
      );
      const filtered = { ...cfg };
      for (const key of requiredColumns) {
        if (typeof key === "string" && missing.includes(String(cfg[key]))) delete filtered[key];
      }
      onLoad(filtered);
    } else {
      setWarning("");
      onLoad(cfg);
    }
    addLog("INFO", `Loaded analysis preset "${presetName}".`, type);
  }

  function remove() {
    if (!selected) return;
    setPresets(deletePreset(selected, type));
    setSelected("");
    addLog("INFO", `Deleted analysis preset "${selected}".`, type);
  }

  return (
    <SectionCard title={t("savedAnalysis")}>
      <div className="space-y-2">
        <div className="flex gap-2">
          <input
            className="h-9 min-w-0 flex-1 rounded-lg border border-border bg-bg px-2 text-[12px] text-text"
            placeholder={t("presetName")}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <Button size="sm" variant="secondary" onClick={save}>
            <Save className="h-3.5 w-3.5" />
            {t("savePreset")}
          </Button>
        </div>
        {presets.length ? (
          <div className="flex gap-2">
            <Select
              value={selected}
              onChange={load}
              options={[
                { value: "", label: t("loadPreset") },
                ...presets.map((p) => ({ value: p.name, label: p.name })),
              ]}
            />
            <Button size="sm" variant="ghost" onClick={remove} disabled={!selected} title="Delete preset">
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        ) : null}
        {warning ? <ValidationNote>{warning}</ValidationNote> : null}
      </div>
    </SectionCard>
  );
}
