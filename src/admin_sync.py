import urllib.request
import json
import re
import random
import time
from urllib.error import HTTPError

# Configuration Supabase directe
SUPABASE_URL = "https://azvlbugdewwjwizksmaq.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImF6dmxidWdkZXd3andpemtzbWFxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODU0MTIzNTgsImV4cCI6MjEwMDk4ODM1OH0.mYEwacqQzwKC2wv0M74C6kuSD9y8J5O4H54wNlGwk08"

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
    
    # Fallback unique si le réseau ou le parsing échoue (jamais SCAN-00000 statique)
    rnd = random.randint(10000, 99999)
    return f"SCAN-{rnd}"

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
        data = json.dumps(payload).encode("utf-8")
        url = f"{SUPABASE_URL}/rest/v1/scans"
        req = urllib.request.Request(url, data=data, headers={
            "Content-Type": "application/json",
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            "Prefer": "resolution=merge-duplicates"
        }, method="POST")

        with urllib.request.urlopen(req, timeout=12) as response:
            return {
                "success": response.status in [200, 201, 204],
                "scan_id": scan_id,
                "mode": "Supabase Direct",
                "status_code": response.status
            }
    except HTTPError as e:
        # En cas de conflit de clé primaire (409) ou d'erreur de doublon, réessayer avec un nouvel ID
        if e.code in [400, 409] and retry_count < 3:
            new_id = f"SCAN-{random.randint(10000, 99999)}"
            scan_data["scan_id"] = new_id
            return transmit_scan_to_supabase(new_id, scan_data, retry_count=retry_count + 1)
        return {
            "success": False,
            "mode": "Supabase HTTPError",
            "status_code": e.code,
            "error": str(e)
        }
    except Exception as e:
        if retry_count < 2:
            new_id = f"SCAN-{random.randint(10000, 99999)}"
            return transmit_scan_to_supabase(new_id, scan_data, retry_count=retry_count + 1)
        return {
            "success": False,
            "mode": "Supabase Error",
            "error": str(e)
        }

def check_for_updates(current_version):
    """
    Vérifie si une nouvelle version est disponible sur GitHub.
    """
    try:
        url = "https://raw.githubusercontent.com/AdamZoda/ANTI/main/version.json"
        req = urllib.request.Request(url, headers={
            "User-Agent": "ANTI-Defense-Scanner/1.0"
        })
        with urllib.request.urlopen(req, timeout=4) as response:
            data = json.loads(response.read().decode("utf-8"))
            latest = data.get("version", current_version)
            download_url = data.get("download_url", "https://github.com/AdamZoda/ANTI/releases")
            if float(latest) > float(current_version):
                return True, latest, download_url
    except Exception:
        pass
    return False, None, None
