import urllib.request
import json

# Configuration Supabase directe
SUPABASE_URL = "https://azvlbugdewwjwizksmaq.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImF6dmxidWdkZXd3andpemtzbWFxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODU0MTIzNTgsImV4cCI6MjEwMDk4ODM1OH0.mYEwacqQzwKC2wv0M74C6kuSD9y8J5O4H54wNlGwk08"

def get_next_scan_id_from_supabase():
    """Récupère le prochain scan_id depuis Supabase en comptant les scans existants."""
    try:
        url = f"{SUPABASE_URL}/rest/v1/scans?select=scan_id&order=scan_id.desc&limit=1"
        req = urllib.request.Request(url, headers={
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}"
        })
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            if data and len(data) > 0:
                last_id = data[0].get("scan_id", "SCAN-00000")
                num = int(last_id.replace("SCAN-", "")) + 1
                return f"SCAN-{num:05d}"
    except Exception:
        pass
    return "SCAN-00000"

def transmit_scan_to_supabase(scan_id, scan_data):
    """
    Envoie le rapport de scan directement à Supabase via l'API REST.
    Plus besoin de serveur Express intermédiaire.
    """
    # Calcul du verdict
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
        "timestamp": scan_data.get("timestamp"),
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

        with urllib.request.urlopen(req, timeout=10) as response:
            return {
                "success": response.status in [200, 201, 204],
                "mode": "Supabase Direct",
                "status_code": response.status
            }
    except Exception as e:
        return {
            "success": False,
            "mode": "Supabase Error",
            "error": str(e)
        }
