import os
import json
import time

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
SCANS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scans_admin")

def load_config():
    if not os.path.exists(CONFIG_PATH):
        default_config = {
            "next_scan_id": 0,
            "admin_url": "https://api.my-anti-server.com/api/v1/scans",
            "admin_key": "ADMIN-SECRET-KEY-2026",
            "app_name": "ANTI Defense System"
        }
        save_config(default_config)
        return default_config
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

def generate_next_scan_id():
    config = load_config()
    current_id_num = config.get("next_scan_id", 0)
    scan_id = f"SCAN-{current_id_num:05d}"
    config["next_scan_id"] = current_id_num + 1
    save_config(config)
    return scan_id

def save_admin_scan(scan_id, scan_data):
    if not os.path.exists(SCANS_DIR):
        os.makedirs(SCANS_DIR, exist_ok=True)
    
    file_path = os.path.join(SCANS_DIR, f"{scan_id}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(scan_data, f, indent=2, ensure_ascii=False)
    return file_path

def get_admin_scan(scan_id):
    file_path = os.path.join(SCANS_DIR, f"{scan_id}.json")
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def list_all_admin_scans():
    if not os.path.exists(SCANS_DIR):
        return []
    scans = []
    for file_name in sorted(os.listdir(SCANS_DIR)):
        if file_name.startswith("SCAN-") and file_name.endswith(".json"):
            file_path = os.path.join(SCANS_DIR, file_name)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    scans.append({
                        "scan_id": data.get("scan_id"),
                        "timestamp": data.get("timestamp"),
                        "hostname": data.get("system_info", {}).get("hostname"),
                        "user": data.get("system_info", {}).get("user"),
                        "risk_score": data.get("risk_summary", {}).get("overall_risk_score"),
                        "threat_level": data.get("risk_summary", {}).get("threat_level"),
                        "processes_scanned": data.get("stats", {}).get("processes_scanned")
                    })
            except Exception:
                pass
    return scans
