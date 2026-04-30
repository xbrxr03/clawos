#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::path::PathBuf;
use std::process::Command;
use std::sync::Mutex;

use tauri::{Manager, WebviewUrl, WebviewWindowBuilder};

fn clawos_dir() -> Result<PathBuf, String> {
    if let Ok(dir) = std::env::var("CLAWOS_DIR") {
        return Ok(PathBuf::from(dir));
    }

    let home = std::env::var("HOME")
        .or_else(|_| std::env::var("USERPROFILE"))
        .map_err(|e| e.to_string())?;
    Ok(PathBuf::from(home).join("clawos"))
}

fn resolve_path(kind: &str) -> Result<PathBuf, String> {
    let root = clawos_dir()?;
    let path = match kind {
        "clawos" => root,
        "config" => root.join("config"),
        "logs" => root.join("logs"),
        "support" => root.join("support"),
        "workspace" => root.join("workspace"),
        _ => return Err(format!("unknown path kind: {kind}")),
    };
    Ok(path)
}

#[tauri::command]
fn reveal_logs() -> Result<String, String> {
    Ok(resolve_path("logs")?.to_string_lossy().to_string())
}

#[tauri::command]
fn service_action(action: String, service: String) -> Result<String, String> {
    let output = Command::new("python3")
        .arg("-c")
        .arg(format!(
            "from clawos_core.service_manager import {action}; ok, detail = {action}('{service}'); print(detail if detail else ('ok' if ok else 'failed'))"
        ))
        .output()
        .map_err(|e| e.to_string())?;

    Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
}

#[tauri::command]
fn create_support_bundle() -> Result<String, String> {
    let output = Command::new("python3")
        .arg("-c")
        .arg(
            "from tools.support.support_bundle import create_support_bundle; print(create_support_bundle())",
        )
        .output()
        .map_err(|e| e.to_string())?;

    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).trim().to_string());
    }

    Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
}

#[tauri::command]
fn open_path(kind: String) -> Result<String, String> {
    let path = resolve_path(&kind)?;
    std::fs::create_dir_all(&path).map_err(|e| e.to_string())?;

    let opener = if cfg!(target_os = "macos") { "open" } else { "xdg-open" };
    let output = Command::new(opener)
        .arg(&path)
        .output()
        .map_err(|e| e.to_string())?;

    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).trim().to_string());
    }

    Ok(path.to_string_lossy().to_string())
}

// ─── Approval overlay ──────────────────────────────────────────────────────
//
// Floating, always-on-top, undecorated window that surfaces pending approvals
// from policyd. Created on demand by `show_approval_overlay`, hidden by
// `hide_approval_overlay`. The window shares the same web frontend as the
// main dashboard but loads the route #/overlay/approval.

const APPROVAL_OVERLAY_LABEL: &str = "approval-overlay";

#[tauri::command]
fn show_approval_overlay(app: tauri::AppHandle) -> Result<String, String> {
    if let Some(win) = app.get_webview_window(APPROVAL_OVERLAY_LABEL) {
        win.show().map_err(|e| e.to_string())?;
        win.set_focus().map_err(|e| e.to_string())?;
        return Ok("shown".to_string());
    }

    let url = WebviewUrl::App("index.html#/overlay/approval".into());
    WebviewWindowBuilder::new(&app, APPROVAL_OVERLAY_LABEL, url)
        .title("Approve task")
        .inner_size(420.0, 240.0)
        .resizable(false)
        .always_on_top(true)
        .decorations(false)
        .skip_taskbar(true)
        .center()
        .visible(true)
        .build()
        .map_err(|e| e.to_string())?;
    Ok("created".to_string())
}

#[tauri::command]
fn hide_approval_overlay(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(win) = app.get_webview_window(APPROVAL_OVERLAY_LABEL) {
        win.hide().map_err(|e| e.to_string())?;
    }
    Ok(())
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            reveal_logs,
            service_action,
            create_support_bundle,
            open_path,
            show_approval_overlay,
            hide_approval_overlay,
        ])
        .run(tauri::generate_context!())
        .expect("error while running ClawOS desktop shell");
}
