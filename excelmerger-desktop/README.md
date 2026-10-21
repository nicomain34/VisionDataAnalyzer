# ExcelMerger Desktop (Tauri + React)

Modern Windows desktop build of ExcelMerger.

## Architecture

- **UI:** React + TypeScript + Vite + Tailwind + Recharts
- **Shell:** Tauri 2 (Windows `.exe` / NSIS installer)
- **Engine:** Python sidecar (`python-engine/`) preserving pandas/openpyxl merge + distribution logic

The legacy Tkinter app in `../excel-combine-gui` remains untouched as a fallback.

## Prerequisites (developers only)

- Node.js 20+
- Rust (stable) + Windows GNU toolchain **or** MSVC Build Tools
  - This machine uses MinGW (`stable-x86_64-pc-windows-gnu`) when MSVC `link.exe` is unavailable
- Python 3.9+ with `pandas`, `openpyxl`, `xlrd`, `numpy`
- `pip install pyinstaller` for the production sidecar

End users only need the built `ExcelMerger.exe` (no Node/Python/Rust).

> **Windows note:** `windres` fails if the project path contains non-ASCII characters (e.g. Cyrillic). Build from an ASCII path such as `C:\dev\excelmerger-desktop` (copy/mirror the folder, then run the commands below).

## Development

```bash
cd excelmerger-desktop
npm install
npm run tauri:dev
```

During `tauri:dev`, the Rust shell starts `python -u python-engine/main.py` as the engine.

## Production build

```bash
# Package Python engine as sidecar (required for offline .exe)
pip install pyinstaller
npm run engine:build

# Build Windows app + NSIS/MSI installers
npm run tauri:build
```

Artifacts appear under `src-tauri/target/release/` (exe) and `src-tauri/target/release/bundle/` (installers).
A convenient copy is also kept in `dist-release/` after a successful build from the ASCII mirror path.

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Vite UI only |
| `npm run tauri:dev` | Desktop app + UI |
| `npm run tauri:build` | Production Windows package |
| `npm run engine:run` | Run Python engine on stdio |
| `npm run engine:build` | PyInstaller sidecar into `src-tauri/binaries` |
