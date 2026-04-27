use std::time::Duration;
use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    Manager, RunEvent, WindowEvent,
};
use tauri_plugin_shell::ShellExt;
use keyring::Entry;

const BACKEND_HEALTH_URL: &str = "http://127.0.0.1:8000/health";
const BACKEND_APP_URL: &str = "http://127.0.0.1:8000/";
const BACKEND_MAX_WAIT_SECS: u64 = 60;
const BACKEND_POLL_INTERVAL_MS: u64 = 500;

#[tauri::command]
fn get_credential(service: String, account: String) -> Result<Option<String>, String> {
    let entry = Entry::new(&service, &account).map_err(|e| e.to_string())?;
    match entry.get_password() {
        Ok(p) => Ok(Some(p)),
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(e) => Err(e.to_string()),
    }
}

#[tauri::command]
fn set_credential(service: String, account: String, password: String) -> Result<(), String> {
    let entry = Entry::new(&service, &account).map_err(|e| e.to_string())?;
    entry.set_password(&password).map_err(|e| e.to_string())
}

#[tauri::command]
fn delete_credential(service: String, account: String) -> Result<(), String> {
    let entry = Entry::new(&service, &account).map_err(|e| e.to_string())?;
    entry.delete_credential().map_err(|e| e.to_string())
}

#[tokio::main]
async fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            get_credential,
            set_credential,
            delete_credential,
        ])
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            // Spawn the Python sidecar
            let mut sidecar = app
                .shell()
                .sidecar("sagemate-server")
                .map_err(|e| {
                    eprintln!("[SageMate] Failed to locate sidecar: {}", e);
                    e
                })?;

            // Inject API keys from system keyring into sidecar environment
            for (env_key, account) in [
                ("SAGEMATE_LLM_API_KEY", "llm_api_key"),
                ("SAGEMATE_VISION_API_KEY", "vision_api_key"),
                ("SAGEMATE_WECHAT_API_KEY", "wechat_api_key"),
            ] {
                if let Ok(Some(val)) = get_credential("sagemate".to_string(), account.to_string()) {
                    sidecar = sidecar.env(env_key, val);
                }
            }

            let (mut rx, child) = sidecar
                .spawn()
                .map_err(|e| {
                    eprintln!("[SageMate] Failed to spawn sidecar: {}", e);
                    e
                })?;

            // Store child process handle for cleanup
            app.manage(SidecarHandle(std::sync::Mutex::new(Some(child))));

            // Poll stdout/stderr of sidecar for debugging
            tauri::async_runtime::spawn(async move {
                while let Some(event) = rx.recv().await {
                    match event {
                        tauri_plugin_shell::process::CommandEvent::Stdout(line) => {
                            println!("[sidecar stdout] {}", String::from_utf8_lossy(&line));
                        }
                        tauri_plugin_shell::process::CommandEvent::Stderr(line) => {
                            eprintln!("[sidecar stderr] {}", String::from_utf8_lossy(&line));
                        }
                        tauri_plugin_shell::process::CommandEvent::Error(e) => {
                            eprintln!("[sidecar error] {}", e);
                        }
                        tauri_plugin_shell::process::CommandEvent::Terminated(payload) => {
                            println!("[sidecar] terminated: code={:?}, signal={:?}", payload.code, payload.signal);
                            break;
                        }
                        _ => {}
                    }
                }
            });

            // Wait for backend to be ready, then show the window
            let app_handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                let client = reqwest::Client::new();
                let max_attempts = BACKEND_MAX_WAIT_SECS * 1000 / BACKEND_POLL_INTERVAL_MS;
                let mut backend_ready = false;

                for attempt in 0..max_attempts {
                    match client.get(BACKEND_HEALTH_URL).send().await {
                        Ok(resp) if resp.status().is_success() => {
                            println!("[SageMate] Backend ready at {}", BACKEND_HEALTH_URL);
                            backend_ready = true;
                            break;
                        }
                        _ => {
                            if attempt % 10 == 0 {
                                println!("[SageMate] Waiting for backend... ({}/{})", attempt, max_attempts);
                            }
                            tokio::time::sleep(Duration::from_millis(BACKEND_POLL_INTERVAL_MS)).await;
                        }
                    }
                }

                if backend_ready {
                    if let Some(window) = app_handle.get_webview_window("main") {
                        // The hidden window may have loaded before the sidecar was ready.
                        // Navigate again after health passes to avoid showing a stale error/blank page.
                        if let Ok(url) = tauri::Url::parse(BACKEND_APP_URL) {
                            let _ = window.navigate(url);
                        }
                        let _ = window.show();
                        let _ = window.set_focus();
                        println!("[SageMate] Window shown");
                    } else {
                        eprintln!("[SageMate] Window 'main' not found — cannot show");
                    }
                } else {
                    eprintln!("[SageMate] Backend failed to start within {}s", BACKEND_MAX_WAIT_SECS);
                }
            });

            // Setup system tray
            let show_i = MenuItem::with_id(app, "show", "Show SageMate", true, None::<&str>)?;
            let quit_i = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show_i, &quit_i])?;

            let tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .show_menu_on_left_click(true)
                .on_menu_event(|app, event| {
                    match event.id().as_ref() {
                        "show" => {
                            if let Some(window) = app.get_webview_window("main") {
                                let _ = window.show();
                                let _ = window.set_focus();
                            }
                        }
                        "quit" => {
                            println!("[SageMate] Quitting via tray menu...");
                            // Kill sidecar before exit
                            if let Some(handle) = app.try_state::<SidecarHandle>() {
                                if let Ok(mut child) = handle.0.lock() {
                                    if let Some(c) = child.take() {
                                        let _ = c.kill();
                                    }
                                }
                            }
                            app.exit(0);
                        }
                        _ => {}
                    }
                })
                .on_tray_icon_event(|tray, event| {
                    if let tauri::tray::TrayIconEvent::Click { button: tauri::tray::MouseButton::Left, .. } = event {
                        let app = tray.app_handle();
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                })
                .build(app)?;

            app.manage(TrayHandle(tray));

            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                // Hide to tray instead of closing
                let _ = window.hide();
                api.prevent_close();
            }
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app, event| {
            match event {
                RunEvent::ExitRequested { api, .. } => {
                    // Kill sidecar on exit
                    if let Some(handle) = app.try_state::<SidecarHandle>() {
                        if let Ok(mut child) = handle.0.lock() {
                            if let Some(c) = child.take() {
                                let _ = c.kill();
                            }
                        }
                    }
                    api.prevent_exit();
                }
                _ => {}
            }
        });
}

// State types for managing sidecar and tray across handlers
struct SidecarHandle(std::sync::Mutex<Option<tauri_plugin_shell::process::CommandChild>>);
#[allow(dead_code)]
struct TrayHandle(tauri::tray::TrayIcon);
