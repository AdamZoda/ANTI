import sys
from src.ui import print_banner, render_progress, print_client_completion
from src.scanner import run_system_scan
from src.admin_sync import get_next_scan_id_from_supabase, transmit_scan_to_supabase

CURRENT_VERSION = "1.6"

def main():
    print_banner()
    
    # 0. Vérification des mises à jour
    from src.admin_sync import check_for_updates
    update_dispo, latest_ver, download_url = check_for_updates(CURRENT_VERSION)
    if update_dispo:
        print(f"\033[91m[!] UNE NOUVELLE MISE À JOUR EST DISPONIBLE (v{latest_ver})\033[0m")
        print("Veuillez télécharger la dernière version officielle pour continuer :")
        print(f"\033[96m► {download_url}\033[0m\n")
        sys.exit(0)

    print("\033[93m[➔] Initialisation de l'analyse système...\033[0m\n")

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

    if result.get("success"):
        print("\033[92m[✓] Données synchronisées avec le serveur de sécurité.\033[0m\n")
    else:
        print("\033[91m[!] Synchronisation échouée — les données seront retransmises.\033[0m\n")

if __name__ == "__main__":
    main()
