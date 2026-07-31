import urllib.request
import json
import re
import random
import time
import os
from urllib.error import HTTPError

# ─────────────────────────────────────────────
# CONFIGURATION SUPABASE
# ─────────────────────────────────────────────
SUPABASE_URL      = "https://azvlbugdewwjwizksmaq.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImF6dmxidWdkZXd3andpemtzbWFxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODU0MTIzNTgsImV4cCI6MjEwMDk4ODM1OH0.mYEwacqQzwKC2wv0M74C6kuSD9y8J5O4H54wNlGwk08"

# ─────────────────────────────────────────────
# CHARGEMENT CONFIG DISCORD WEBHOOK
# ─────────────────────────────────────────────
# Le chemin est résolu relativement à l'emplacement de ce fichier
# (fonctionne aussi bien en dev qu'en EXE PyInstaller)
_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")

_DISCORD_WEBHOOK_URL = None

def _load_webhook_config():
    global _DISCORD_WEBHOOK_URL
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        _DISCORD_WEBHOOK_URL = cfg.get("webhook", {}).get("url")
    except Exception:
        _DISCORD_WEBHOOK_URL = None

_load_webhook_config()

# ─────────────────────────────────────────────
# SCAN ID SEQUENTIEL
# ─────────────────────────────────────────────
def get_next_scan_id_from_supabase():
    """Récupère le prochain scan_id séquentiel depuis Supabase."""
    try:
        url = f"{SUPABASE_URL}/rest/v1/scans?select=scan_id&order=timestamp.desc&limit=10"
        req = urllib.request.Request(url, headers={
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}"
        })
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
            if data and len(data) > 0:
                for item in data:
                    sid = item.get("scan_id", "")
                    if sid.startswith("SCAN-"):
                        digits = re.sub(r'\D', '', sid)
                        if digits:
                            num = int(digits) + 1
                            return f"SCAN-{num:05d}"
    except Exception:
        pass

    rnd = random.randint(10000, 99999)
    return f"SCAN-{rnd}"

# ─────────────────────────────────────────────
# ENVOI VERS SUPABASE
# ─────────────────────────────────────────────
def transmit_scan_to_supabase(scan_id, scan_data, retry_count=0):
    """
    Envoie le rapport de scan directement à Supabase via l'API REST.
    Si le scan_id existe déjà, régénère un ID unique et réessaie automatiquement.
    """
    score = scan_data.get("risk_summary", {}).get("overall_risk_score", 0)
    if score >= 60:
        verdict = "CHEATER"
    elif score >= 30:
        verdict = "ANORMAL"
    else:
        verdict = "CLEAN"

    if "risk_summary" in scan_data:
        scan_data["risk_summary"]["verdict"] = verdict

    payload = {
        "scan_id"         : scan_id,
        "hwid"            : scan_data.get("hwid") or scan_data.get("system_info", {}).get("hwid", "UNKNOWN"),
        "timestamp"       : scan_data.get("timestamp") or time.strftime("%Y-%m-%d %H:%M:%S"),
        "system_info"     : scan_data.get("system_info", {}),
        "disk_performance": scan_data.get("disk_performance", {}),
        "stats"           : scan_data.get("stats", {}),
        "risk_summary"    : scan_data.get("risk_summary", {}),
        "applications"    : scan_data.get("applications", [])
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        url  = f"{SUPABASE_URL}/rest/v1/scans"
        req  = urllib.request.Request(url, data=data, headers={
            "Content-Type" : "application/json",
            "apikey"       : SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            "Prefer"       : "resolution=merge-duplicates"
        }, method="POST")

        with urllib.request.urlopen(req, timeout=12) as response:
            return {
                "success"    : response.status in [200, 201, 204],
                "scan_id"    : scan_id,
                "mode"       : "Supabase Direct",
                "status_code": response.status,
                "verdict"    : verdict
            }
    except HTTPError as e:
        if e.code in [400, 409] and retry_count < 3:
            new_id = f"SCAN-{random.randint(10000, 99999)}"
            scan_data["scan_id"] = new_id
            return transmit_scan_to_supabase(new_id, scan_data, retry_count=retry_count + 1)
        return {"success": False, "mode": "Supabase HTTPError", "status_code": e.code, "error": str(e)}
    except Exception as e:
        if retry_count < 2:
            new_id = f"SCAN-{random.randint(10000, 99999)}"
            return transmit_scan_to_supabase(new_id, scan_data, retry_count=retry_count + 1)
        return {"success": False, "mode": "Supabase Error", "error": str(e)}

# ─────────────────────────────────────────────
# NOTIFICATION DISCORD WEBHOOK
# ─────────────────────────────────────────────
def send_to_discord(scan_id, scan_data, verdict):
    """
    Envoie un rapport de scan formaté dans un salon Discord via webhook.
    Ne crash jamais — erreurs silencieuses.
    """
    if not _DISCORD_WEBHOOK_URL:
        return

    si    = scan_data.get("system_info", {})
    risk  = scan_data.get("risk_summary", {})
    score = risk.get("overall_risk_score", 0)

    # Couleur selon verdict
    color_map = {"CHEATER": 0xFF4444, "ANORMAL": 0xFFAA00, "CLEAN": 0x44FF88}
    color = color_map.get(verdict, 0x888888)

    # Icône selon verdict
    icon_map = {"CHEATER": "🔴", "ANORMAL": "🟡", "CLEAN": "🟢"}
    icon = icon_map.get(verdict, "⚪")

    apps         = scan_data.get("applications", [])
    flagged_apps = [a for a in apps if (a.get("risk_assessment", {}).get("risk_score") or 0) >= 60]
    flagged_str  = "\n".join(f"• `{a.get('app_name', 'inconnu')}` — score {a.get('risk_assessment', {}).get('risk_score', 0)}" for a in flagged_apps[:5]) or "Aucune"

    embed = {
        "title"      : f"{icon} ANTI Scanner — {verdict}",
        "description": f"Scan `{scan_id}` terminé.",
        "color"      : color,
        "fields"     : [
            {"name": "🖥️ Machine",    "value": f"`{si.get('hostname', 'N/A')}`",             "inline": True},
            {"name": "👤 Utilisateur","value": f"`{si.get('user', 'N/A')}`",                  "inline": True},
            {"name": "🔑 HWID",       "value": f"`{si.get('hwid', 'N/A')}`",                  "inline": False},
            {"name": "📊 Score",      "value": f"`{score}/100`",                              "inline": True},
            {"name": "⚖️ Verdict",    "value": f"`{verdict}`",                                "inline": True},
            {"name": "🖥️ OS",         "value": f"`{si.get('os_version', 'N/A')}`",            "inline": False},
            {"name": "⚠️ Apps Suspectes (top 5)", "value": flagged_str,                      "inline": False},
        ],
        "footer"     : {"text": f"ANTI Defense System v1.9 | {scan_data.get('timestamp', '')}"}
    }

    payload = json.dumps({"embeds": [embed], "username": "ANTI Defense"}).encode("utf-8")

    try:
        req = urllib.request.Request(
            _DISCORD_WEBHOOK_URL,
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=6)
    except Exception:
        pass  # Ne jamais crasher le scanner à cause du webhook

# ─────────────────────────────────────────────
# VÉRIFICATION DE MISE À JOUR
# ─────────────────────────────────────────────
def check_for_updates(current_version):
    """Vérifie si une nouvelle version est disponible sur GitHub."""
    try:
        url = "https://raw.githubusercontent.com/AdamZoda/ANTI/main/version.json"
        req = urllib.request.Request(url, headers={"User-Agent": "ANTI-Defense-Scanner/1.0"})
        with urllib.request.urlopen(req, timeout=4) as response:
            data         = json.loads(response.read().decode("utf-8"))
            latest       = data.get("version", current_version)
            download_url = data.get("download_url", "https://github.com/AdamZoda/ANTI/releases")
            if float(latest) > float(current_version):
                return True, latest, download_url
    except Exception:
        pass
    return False, None, None