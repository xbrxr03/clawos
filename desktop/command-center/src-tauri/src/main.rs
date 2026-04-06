#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::Command;
use std::path::PathBuf;

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

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![reveal_logs, service_action, create_support_bundle, open_path])
        .run(tauri::generate_context!())
        .expect("error while running ClawOS desktop shell");
}
