import sys
import os
from src.ui import print_banner, render_progress, print_client_completion
from src.scanner import run_system_scan
from src.admin_sync import (
    get_next_scan_id_from_supabase,
    transmit_scan_to_supabase,
    send_to_discord
)

CURRENT_VERSION = "2.0"

def main():
    print_banner()

    # 1. Récupérer le prochain scan_id depuis Supabase
    scan_id = get_next_scan_id_from_supabase()

    # 2. Exécution du scan avec affichage dynamique
    def update_ui(stage, percent, info):
        render_progress(stage, percent, info)

    scan_data = run_system_scan(progress_callback=update_ui)
    scan_data["scan_id"] = scan_id

    # 3. Transmission vers Supabase — récupère le verdict normalisé
    result  = transmit_scan_to_supabase(scan_id, scan_data)
    verdict = result.get("verdict", scan_data.get("risk_summary", {}).get("verdict", "CLEAN"))

    # 4. Notification Discord webhook (silencieuse si webhook absent)
    send_to_discord(scan_id, scan_data, verdict)

    # 5. Affichage final anonymisé pour le Client
    print_client_completion(scan_id)

if __name__ == "__main__":
    main()

if hasattr(sys, '_MEIPASS'):
    base_path = sys._MEIPASS
else:
    base_path = os.path.abspath(".")

config_path = os.path.join(base_path, "config.json")