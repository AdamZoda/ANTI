import sys
import os
import shutil
import tempfile
import subprocess
import time
import threading
from src.ui import print_banner, render_progress, print_client_completion
from src.scanner import run_system_scan
from src.admin_sync import (
    get_next_scan_id_from_supabase,
    transmit_scan_to_supabase,
    send_to_discord,
    check_for_updates
)

CURRENT_VERSION = "2.8"


def pre_clean_environment():
    """1. Nettoyage de l'environnement au démarrage de l'EXE."""
    try:
        temp_dir = tempfile.gettempdir()
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        appdata = os.environ.get("APPDATA", "")

        targets = [
            os.path.join(local_appdata, "AntiScan"),
            os.path.join(temp_dir, "AntiScan"),
            os.path.join(appdata, "AntiScan"),
        ]

        for target in targets:
            if os.path.exists(target):
                shutil.rmtree(target, ignore_errors=True)
    except Exception:
        pass


def self_destruct(delay_sec=2):
    """2. Auto-destruction silencieuse post-scan de l'exécutable et de ses traces."""
    try:
        if getattr(sys, 'frozen', False):
            current_exe = sys.executable
            exe_dir = os.path.dirname(current_exe)
            
            # Script cmd en arrière-plan qui force la fin de l'exe si encore ouvert, puis le supprime
            exe_name = os.path.basename(current_exe)
            cmd = f'timeout /t {delay_sec} /nobreak >nul & taskkill /f /im "{exe_name}" 2>nul & del /f /q /a "{current_exe}"'
            cmd += ' & rd /s /q "%LOCALAPPDATA%\\AntiScan" 2>nul'
            cmd += ' & rd /s /q "%TEMP%\\AntiScan" 2>nul'

            subprocess.Popen(f'cmd.exe /c {cmd}', shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception:
        pass


def arm_watchdog_timer(max_lifetime_sec=300):
    """Lance un timer d'auto-destruction garanti (Watchdog). Si l'application plante ou est bloquée > 5 min, destruction forcée."""
    def _watchdog():
        time.sleep(max_lifetime_sec)
        self_destruct(delay_sec=1)
        os._exit(1)

    t = threading.Thread(target=_watchdog, daemon=True)
    t.start()


from src.gui_app import launch_gui_app

def run_full_scan_process(progress_callback):
    """Exécute le scan système et transmet à Supabase/Discord."""
    # 1. Récupérer le prochain scan_id depuis Supabase
    scan_id = get_next_scan_id_from_supabase()

    # 2. Exécution du scan
    scan_data = run_system_scan(progress_callback=progress_callback)
    scan_data["scan_id"] = scan_id

    # 3. Transmission vers Supabase
    progress_callback("Transmission Data", 98, "Transmission sécurisée vers la base de données...")
    result  = transmit_scan_to_supabase(scan_id, scan_data)
    verdict = result.get("verdict", scan_data.get("risk_summary", {}).get("verdict", "CLEAN"))

    # 4. Notification Discord webhook
    send_to_discord(scan_id, scan_data, verdict)

    # 5. Loader à 100%
    progress_callback("Scan Terminé", 100, f"Rapport sécurisé transmis avec succès (ID: {scan_id})")


def check_and_perform_update():
    """Vérifie s'il y a une différence de version, la télécharge et l'applique silencieusement en arrière-plan."""
    try:
        has_update, latest_ver, download_url = check_for_updates(CURRENT_VERSION)
        # Si la version distante existe et est différente de la version locale
        if latest_ver and latest_ver != CURRENT_VERSION and download_url:
            if getattr(sys, 'frozen', False):
                current_exe = sys.executable
                exe_dir = os.path.dirname(current_exe)
                new_exe_tmp = os.path.join(exe_dir, "anti-scan.tmp")

                # 1. Télécharger silencieusement le nouvel exécutable
                import urllib.request
                import ssl
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE

                req = urllib.request.Request(download_url, headers={"User-Agent": "ANTI-Defense-Scanner/1.0"})
                with urllib.request.urlopen(req, context=ctx, timeout=30) as response:
                    with open(new_exe_tmp, "wb") as f:
                        f.write(response.read())

                # Vérifier que le fichier fait une taille décente (> 1 Mo)
                if os.path.exists(new_exe_tmp) and os.path.getsize(new_exe_tmp) > 1000000:
                    # 2. Lancer la commande de substitution asynchrone et relancer le nouveau process
                    exe_name = os.path.basename(current_exe)
                    cmd = (
                        f'timeout /t 1 /nobreak >nul & '
                        f'taskkill /f /im "{exe_name}" 2>nul & '
                        f'move /y "{new_exe_tmp}" "{current_exe}" 2>nul & '
                        f'start "" "{current_exe}" & '
                        f'del /f /q "{new_exe_tmp}" 2>nul'
                    )
                    subprocess.Popen(f'cmd.exe /c {cmd}', shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    os._exit(0) # Quitter immédiatement
    except Exception:
        pass # Si l'update échoue, on continue normalement sur l'ancienne version


def main():
    # 0. Réduire la priorité du processus pour éviter de faire ramer le PC du joueur
    import psutil
    try:
        p = psutil.Process(os.getpid())
        p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception:
        pass

    # 1. Vérifier et exécuter silencieusement la mise à jour s'il y a lieu
    check_and_perform_update()

    # 2. Armer immédiatement le Watchdog de sécurité (Timer de secours global)
    arm_watchdog_timer(max_lifetime_sec=300)

    # 3. Nettoyage pré-scan immédiat
    pre_clean_environment()

    # 4. Lancement de l'interface graphique Native GUI
    def on_complete():
        # Succès : suppression propre dans 3 secondes
        time.sleep(3)
        self_destruct(delay_sec=1)
        os._exit(0)

    def on_crash():
        # Erreur / Crash : armer le compte à rebours d'auto-destruction de 30 secondes
        self_destruct(delay_sec=30)

    launch_gui_app(run_full_scan_process, on_complete, on_crash_callback=on_crash)


if __name__ == "__main__":
    main()