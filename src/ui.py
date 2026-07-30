import sys
import os
import time
import threading

SHIELD_ICON = "🛡️ "

BANNER_LOGO = f"""\033[96m
  ╔══════════════════════════════════════════════════════════════════════════════╗
  ║  █████╗ ███╗  ██╗████████╗██╗    {SHIELD_ICON} ANTI DEFENSE SYSTEM v1.6         ║
  ║ ██╔══██╗████╗ ██║╚══██╔══╝██║    System Integrity & Telemetry Scanner     ║
  ║ ███████║██╔██╗██║   ██║   ██║    Multi-Drive · USB Forensics · NTFS USN  ║
  ║ ██╔══██║██║╚████║   ██║   ██║                                             ║
  ║ ██║  ██║██║ ╚███║   ██║   ╚═╝    100% Defensive Security Engine          ║
  ╚══════════════════════════════════════════════════════════════════════════════╝
\033[0m"""

# ANSI helpers
_RESET  = "\033[0m"
_CYAN   = "\033[96m"
_GREEN  = "\033[92m"
_YELLOW = "\033[93m"
_DIM    = "\033[2m"
_BOLD   = "\033[1m"
_UP     = "\033[1A"
_ERASE  = "\033[2K"

def _clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def print_banner():
    """Affiche le banner ASCII, puis l'efface après 1.5 secondes."""
    print(BANNER_LOGO)
    time.sleep(1.5)
    # Effacer proprement le banner (nb de lignes = 10)
    for _ in range(10):
        sys.stdout.write(_UP + _ERASE)
    sys.stdout.flush()

# ── Progress spinner state ──
_spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
_spinner_idx    = 0
_last_stage     = ""
_last_pct       = 0

def render_progress(stage, percent, extra_info=""):
    """
    Loader minimaliste :
    • Barre mince + spinner + couleur par phase
    • Ligne unique qui se met à jour in-place (\\r)
    """
    global _spinner_idx, _last_stage, _last_pct

    _spinner_idx = (_spinner_idx + 1) % len(_spinner_frames)
    spinner = _spinner_frames[_spinner_idx]

    bar_width = 28
    filled = int(bar_width * percent // 100)
    bar = "━" * filled + "╌" * (bar_width - filled)

    # Couleur selon avancement
    if percent >= 100:
        color = _GREEN
        spinner = "✓"
    elif percent >= 70:
        color = _CYAN
    elif percent >= 40:
        color = "\033[94m"   # bleu
    else:
        color = _YELLOW

    # Tronquer extra_info si trop long
    info_display = extra_info[:42] if extra_info else ""

    line = (
        f"\r{color}{spinner}{_RESET} "
        f"{color}[{bar}]{_RESET} "
        f"{_BOLD}{percent:3d}%{_RESET}  "
        f"{_DIM}{stage:<22}{_RESET}  "
        f"\033[37m{info_display:<44}{_RESET}"
    )

    sys.stdout.write(line)
    sys.stdout.flush()

    if percent >= 100:
        sys.stdout.write("\n")

def print_client_completion(scan_id):
    """Message final minimaliste — ne révèle rien de sensible."""
    sys.stdout.write("\n")
    # Ligne simple, sobre
    print(f"  {_GREEN}✓{_RESET}  {_BOLD}Analyse terminée{_RESET}  {_DIM}·{_RESET}  "
          f"\033[96m{scan_id}{_RESET}  {_DIM}· chiffré & transmis{_RESET}")
    sys.stdout.write("\n")

def print_admin_report(scan_data):
    print("\n" + "═"*80)
    print(f"{_YELLOW}{SHIELD_ICON} RAPPORT ADMINISTRATEUR — SCAN ID: {scan_data.get('scan_id')}{_RESET}")
    print("═"*80)

    sys_info = scan_data.get("system_info", {})
    stats    = scan_data.get("stats", {})
    risk     = scan_data.get("risk_summary", {})
    disk     = scan_data.get("disk_performance", {})

    print(f"Hôte: {sys_info.get('hostname')} | Util: {sys_info.get('user')} | {scan_data.get('timestamp')}")
    print(f"RAM: {sys_info.get('ram_gb')} GB | Disque: {disk.get('read_speed_mb_s')} MB/s")
    print(f"Apps: {stats.get('applications_count')} ({stats.get('processes_scanned')} PIDs) | DLLs: {stats.get('total_dlls_scanned')}")
    print("─" * 80)

    score = risk.get("overall_risk_score", 0)
    threat = risk.get("threat_level", "INCONNU")

    color = _GREEN
    if score >= 60:
        color = "\033[91m"
    elif score >= 30:
        color = _YELLOW

    print(f"SCORE : {color}{score}/100 ({threat}){_RESET}")
    print(f"Apps Suspectes : {risk.get('suspicious_applications_count')}  |  Observations : {risk.get('total_observations_count')}")
    print("═"*80)

    apps = scan_data.get("applications", [])
    suspicious = [a for a in apps if a.get("risk_assessment", {}).get("risk_score", 0) >= 30]

    if suspicious:
        print(f"\n\033[91m[!] APPLICATIONS SUSPECTES :{_RESET}")
        for a in suspicious:
            r   = a.get("risk_assessment", {})
            sig = a.get("signature", {})
            pids_str = ", ".join(str(p) for p in a.get("pids", [])[:5])
            if len(a.get("pids", [])) > 5:
                pids_str += "…"
            print(f"  • {_BOLD}{a.get('app_name')}{_RESET}  Score:{r.get('risk_score')}  |  {a.get('instances_count')}x  PIDs:[{pids_str}]")
            print(f"    {_DIM}{a.get('exe_path')}{_RESET}")
            for obs in r.get("observations", []):
                sev_color = "\033[91m" if obs.get('severity') == 'CRITICAL' else _YELLOW
                print(f"    └─ {sev_color}[{obs.get('severity')}]{_RESET} {obs.get('title')} : {_DIM}{obs.get('description')}{_RESET}")
            print()
    else:
        print(f"\n{_GREEN}[✓] Aucune application suspecte détectée.{_RESET}\n")
