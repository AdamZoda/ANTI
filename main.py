import sys
from src.ui import print_banner, render_progress, print_client_completion
from src.scanner import run_system_scan
from src.admin_sync import get_next_scan_id_from_supabase, transmit_scan_to_supabase

CURRENT_VERSION = "1.7"

def main():
    print_banner()
    
    # 0. Vérification / Log version (silencieuse)
    # L'installer se charge déjà de télécharger la dernière version depuis GitHub.


    # 1. Récupérer le prochain scan_id depuis Supabase
    scan_id = get_next_scan_id_from_supabase()

    # 2. Exécution du scan avec affichage dynamique
    def update_ui(stage, percent, info):
        render_progress(stage, percent, info)

    scan_data = run_system_scan(progress_callback=update_ui)
    scan_data["scan_id"] = scan_id

    # 3. Transmission directe vers Supabase
    result = transmit_scan_to_supabase(scan_id, scan_data)

    # 4. Affichage final anonymisé pour le Client
    print_client_completion(scan_id)

    # Sync status — masqué côté client (admin seulement)
    _ = result  # résultat loggué côté serveur uniquement

if __name__ == "__main__":
    main()
