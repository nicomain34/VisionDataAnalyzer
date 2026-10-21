use once_cell::sync::Lazy;
use parking_lot::Mutex;
use serde_json::{json, Value};
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::mpsc::{channel, Receiver, Sender};
use std::thread;
use tauri::{AppHandle, Emitter, Manager};
use tauri_plugin_dialog::DialogExt;

struct EngineState {
  child: Option<Child>,
  stdin: Option<ChildStdin>,
  response_rx: Option<Receiver<Value>>,
}

impl Default for EngineState {
  fn default() -> Self {
    Self {
      child: None,
      stdin: None,
      response_rx: None,
    }
  }
}

static ENGINE: Lazy<Mutex<EngineState>> = Lazy::new(|| Mutex::new(EngineState::default()));

fn engine_command(app: &AppHandle) -> Command {
  // Dev: python python-engine/main.py from project root
  // Prod: bundled sidecar excelmerger-engine
  let mut candidates: Vec<PathBuf> = Vec::new();

  if let Ok(resource) = app.path().resource_dir() {
    candidates.push(resource.join("excelmerger-engine.exe"));
    candidates.push(resource.join("binaries").join("excelmerger-engine.exe"));
  }
  if let Ok(exe_dir) = app.path().executable_dir() {
    candidates.push(exe_dir.join("excelmerger-engine.exe"));
    candidates.push(exe_dir.join("binaries").join("excelmerger-engine.exe"));
  }

  for cand in candidates {
    if cand.exists() {
      return Command::new(cand);
    }
  }

  let mut cmd = Command::new("python");
  // Resolve ../python-engine/main.py relative to cwd during `tauri dev`
  let script = PathBuf::from("python-engine").join("main.py");
  cmd.arg("-u").arg(script);
  cmd
}

fn ensure_engine(app: &AppHandle) -> Result<(), String> {
  let mut st = ENGINE.lock();
  if st.stdin.is_some() {
    return Ok(());
  }

  let mut cmd = engine_command(app);
  cmd.stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::piped());
  #[cfg(target_os = "windows")]
  {
    use std::os::windows::process::CommandExt;
    cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW
  }

  let mut child = cmd.spawn().map_err(|e| {
    format!(
      "Failed to start Python engine: {e}. Ensure Python is available in PATH for development, or build the sidecar."
    )
  })?;

  let stdin = child.stdin.take().ok_or("No stdin for engine")?;
  let stdout = child.stdout.take().ok_or("No stdout for engine")?;
  let app_handle = app.clone();
  let (tx, rx): (Sender<Value>, Receiver<Value>) = channel();

  thread::spawn(move || {
    let reader = BufReader::new(stdout);
    for line in reader.lines().flatten() {
      if line.trim().is_empty() {
        continue;
      }
      if let Ok(val) = serde_json::from_str::<Value>(&line) {
        if val.get("event").and_then(|v| v.as_str()) == Some("progress") {
          let _ = app_handle.emit("engine-progress", val);
        } else {
          let _ = tx.send(val);
        }
      }
    }
  });

  st.child = Some(child);
  st.stdin = Some(stdin);
  st.response_rx = Some(rx);
  Ok(())
}

fn engine_request_blocking(
  app: AppHandle,
  method: String,
  params: Value,
  id: u64,
) -> Result<Value, String> {
  ensure_engine(&app)?;
  let mut st = ENGINE.lock();

  let req = json!({ "id": id, "method": method, "params": params });
  {
    let stdin = st.stdin.as_mut().ok_or("Engine stdin missing")?;
    writeln!(stdin, "{}", req.to_string()).map_err(|e| e.to_string())?;
    stdin.flush().map_err(|e| e.to_string())?;
  }

  let rx = st
    .response_rx
    .as_ref()
    .ok_or("Engine response channel missing")?;

  // Wait for matching response id
  loop {
    let msg = rx
      .recv_timeout(std::time::Duration::from_secs(4 * 60 * 60))
      .map_err(|_| "Engine timed out".to_string())?;
    if msg.get("id").and_then(|v| v.as_u64()) == Some(id) {
      return Ok(msg);
    }
  }
}

/// The wait runs off the UI thread. A long save used to freeze the window
/// ("Not responding"), and clicking that frozen window closed the process.
#[tauri::command]
async fn engine_request(
  app: AppHandle,
  method: String,
  params: Value,
  id: u64,
) -> Result<Value, String> {
  tauri::async_runtime::spawn_blocking(move || engine_request_blocking(app, method, params, id))
    .await
    .map_err(|e| format!("Engine task failed: {e}"))?
}

fn path_to_string(path: tauri_plugin_dialog::FilePath) -> String {
  path
    .into_path()
    .map(|p| p.to_string_lossy().into_owned())
    .unwrap_or_default()
}

#[tauri::command]
fn pick_folder(app: AppHandle) -> Result<Option<String>, String> {
  let path = app.dialog().file().blocking_pick_folder();
  Ok(path.map(path_to_string).filter(|s| !s.is_empty()))
}

#[tauri::command]
fn pick_files(app: AppHandle) -> Result<Vec<String>, String> {
  let files = app
    .dialog()
    .file()
    .add_filter("Excel/CSV", &["xlsx", "xls", "xlsm", "csv"])
    .blocking_pick_files();
  Ok(
    files
      .unwrap_or_default()
      .into_iter()
      .map(path_to_string)
      .filter(|s| !s.is_empty())
      .collect(),
  )
}

#[tauri::command]
fn pick_save(app: AppHandle, default_name: String) -> Result<Option<String>, String> {
  let path = app
    .dialog()
    .file()
    .set_file_name(&default_name)
    .add_filter("Excel", &["xlsx"])
    .add_filter("CSV", &["csv"])
    .blocking_save_file();
  Ok(path.map(path_to_string).filter(|s| !s.is_empty()))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  tauri::Builder::default()
    .plugin(tauri_plugin_dialog::init())
    .plugin(tauri_plugin_shell::init())
    .setup(|app| {
      if cfg!(debug_assertions) {
        app.handle().plugin(
          tauri_plugin_log::Builder::default()
            .level(log::LevelFilter::Info)
            .build(),
        )?;
      }
      let _ = ensure_engine(app.handle());
      Ok(())
    })
    .invoke_handler(tauri::generate_handler![
      engine_request,
      pick_folder,
      pick_files,
      pick_save
    ])
    .run(tauri::generate_context!())
    .expect("error while running ExcelMerger");
}
