import type { AnalysisPreset } from "./analysisTypes";

const KEY = "excelmerger.analysisPresets";

export function loadPresets(type?: string): AnalysisPreset[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as AnalysisPreset[];
    const list = Array.isArray(parsed) ? parsed : [];
    return type ? list.filter((p) => p.type === type) : list;
  } catch {
    return [];
  }
}

function writeAll(presets: AnalysisPreset[]) {
  localStorage.setItem(KEY, JSON.stringify(presets.slice(0, 60)));
}

/** Presets store configuration only — never dataset rows. */
export function savePreset(preset: AnalysisPreset): AnalysisPreset[] {
  const name = preset.name.trim();
  if (!name) return loadPresets(preset.type);
  const all = loadPresets().filter((p) => !(p.name === name && p.type === preset.type));
  all.unshift({ ...preset, name, savedAt: new Date().toISOString() });
  writeAll(all);
  return loadPresets(preset.type);
}

export function deletePreset(name: string, type: string): AnalysisPreset[] {
  writeAll(loadPresets().filter((p) => !(p.name === name && p.type === type)));
  return loadPresets(type);
}

/** Columns referenced by a preset that no longer exist in the loaded dataset. */
export function missingColumns(required: (string | undefined)[], available: string[]): string[] {
  const set = new Set(available);
  return required.filter((c): c is string => Boolean(c) && !set.has(c as string));
}
