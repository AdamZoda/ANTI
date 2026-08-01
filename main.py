import sys
import os
import traceback
import tempfile

# ──────────────────────────────────────────────────────────────────────────
# CRASH LOGGER — défini AVANT tout autre import
# ──────────────────────────────────────────────────────────────────────────
def _write_crash_log(tb_str):
    try:
        log_path = os.path.join(tempfile.gettempdir(), "anti-crash.log")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(tb_str)
    except Exception:
        pass


# 0. Configuration du chemin DLL Windows pour les extensions C (psutil, etc.) sous PyInstaller
if getattr(sys, 'frozen', False):
    mei_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    if hasattr(os, 'add_dll_directory') and os.path.exists(mei_dir):
        try:
            os.add_dll_directory(mei_dir)
        except Exception:
            pass
    if mei_dir not in sys.path:
        sys.path.insert(0, mei_dir)

# ── Imports stdlib uniquement ──────────────────────────────────────────────
try:
    import shutil
    import subprocess
    import time
    import threading
except Exception:
    _write_crash_log(traceback.format_exc())
    os._exit(1)

CURRENT_VERSION = "2.9"


def pre_clean_environment():
    """Nettoyage de l'environnement au démarrage de l'EXE."""
    try:
        temp_dir = tempfile.gettempdir()
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        appdata = os.environ.get("APPDATA", "")
        for target in [
            os.path.join(local_appdata, "AntiScan"),
            os.path.join(temp_dir, "AntiScan"),
            os.path.join(appdata, "AntiScan"),
        ]:
            if os.path.exists(target):
                shutil.rmtree(target, ignore_errors=True)
    except Exception:
        pass


def self_destruct(delay_sec=2):
    """Auto-destruction silencieuse post-scan de l'exécutable et de ses traces."""
    try:
        if getattr(sys, 'frozen', False):
            current_exe = sys.executable
            exe_name = os.path.basename(current_exe)
            cmd = (
                f'timeout /t {delay_sec} /nobreak >nul'
                f' & taskkill /f /im "{exe_name}" 2>nul'
                f' & del /f /q /a "{current_exe}"'
                f' & rd /s /q "%LOCALAPPDATA%\\AntiScan" 2>nul'
                f' & rd /s /q "%TEMP%\\AntiScan" 2>nul'
            )
            subprocess.Popen(f'cmd.exe /c {cmd}', shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception:
        pass


def arm_watchdog_timer(max_lifetime_sec=300):
    """Watchdog : si l'application plante > 5 min, destruction forcée."""
    def _watchdog():
        time.sleep(max_lifetime_sec)
        self_destruct(delay_sec=1)
        os._exit(1)
    threading.Thread(target=_watchdog, daemon=True).start()


def check_and_perform_update():
    """Vérifie et applique silencieusement une mise à jour si disponible."""
    try:
        from src.admin_sync import check_for_updates
        has_update, latest_ver, download_url = check_for_updates(CURRENT_VERSION)
        if latest_ver and latest_ver != CURRENT_VERSION and download_url:
            if getattr(sys, 'frozen', False):
                current_exe = sys.executable
                exe_dir = os.path.dirname(current_exe)
                new_exe_tmp = os.path.join(exe_dir, "anti-scan.tmp")

                import urllib.request, ssl
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                req = urllib.request.Request(download_url, headers={"User-Agent": "ANTI-Defense-Scanner/1.0"})
                with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
                    with open(new_exe_tmp, "wb") as f:
                        f.write(resp.read())

                if os.path.exists(new_exe_tmp) and os.path.getsize(new_exe_tmp) > 1000000:
                    exe_name = os.path.basename(current_exe)
                    cmd = (
                        f'timeout /t 1 /nobreak >nul'
                        f' & taskkill /f /im "{exe_name}" 2>nul'
                        f' & move /y "{new_exe_tmp}" "{current_exe}" 2>nul'
                        f' & start "" "{current_exe}"'
                        f' & del /f /q "{new_exe_tmp}" 2>nul'
                    )
                    subprocess.Popen(f'cmd.exe /c {cmd}', shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    os._exit(0)
    except Exception:
        pass


def main():
    # Réduire la priorité du processus
    try:
        import ctypes
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000)
    except Exception:
        pass

    # Imports des modules internes (lazy — ici seulement)
    try:
        from src.ui import print_banner, render_progress, print_client_completion
        from src.scanner import run_system_scan
        from src.admin_sync import (
            get_next_scan_id_from_supabase,
            transmit_scan_to_supabase,
            send_to_discord,
        )
    except Exception:
        _write_crash_log(traceback.format_exc())
        os._exit(1)

    # 1. Mise à jour silencieuse
    check_and_perform_update()

    # 2. Watchdog
    arm_watchdog_timer(max_lifetime_sec=300)

    # 3. Nettoyage pré-scan
    pre_clean_environment()

    # 4. Affichage banner terminal
    print_banner()

    # 5. Récupération du scan_id
    scan_id = get_next_scan_id_from_supabase()

    # 6. Scan système avec progress bar terminal
    scan_data = run_system_scan(progress_callback=render_progress)
    scan_data["scan_id"] = scan_id

    # 7. Transmission Supabase
    render_progress("Transmission", 98, "Envoi sécurisé vers la base de données...")
    result  = transmit_scan_to_supabase(scan_id, scan_data)
    verdict = result.get("verdict", scan_data.get("risk_summary", {}).get("verdict", "CLEAN"))

    # 8. Notification Discord
    send_to_discord(scan_id, scan_data, verdict)

    # 9. Affichage final
    render_progress("Terminé", 100, f"Rapport transmis (ID: {scan_id})")
    print_client_completion(scan_id)

    # 10. Auto-destruction après 3 secondes
    time.sleep(3)
    self_destruct(delay_sec=1)
    os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        _write_crash_log(traceback.format_exc())
        os._exit(1)
