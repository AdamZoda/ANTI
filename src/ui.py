import sys
import os
import time

SHIELD_ICON = "🛡️ "

# Magnifique ASCII Art "ANTI" 3D turquoise
BANNER_LOGO = f"""\033[96m
================================================================================
   █████╗ ███╗   ██╗████████╗██╗     {SHIELD_ICON} ANTI DEFENSE SYSTEM
  ██╔══██╗████╗  ██║╚══██╔══╝██║     System Integrity & Telemetry Scanner
  ███████║██╔██╗ ██║   ██║   ██║     Version 2.2 (Discord Webhook + Forensique USB)
  ██╔══██║██║╚██╗██║   ██║   ██║     100% Defensive Security Engine
  ██║  ██║██║ ╚████║   ██║   ██║
  ╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝   ╚═╝
================================================================================
\033[0m"""

_RESET  = "\033[0m"
_CYAN   = "\033[96m"
_GREEN  = "\033[92m"
_YELLOW = "\033[93m"
_DIM    = "\033[2m"
_BOLD   = "\033[1m"

def print_banner():
    """Affiche le magnifique Banner ASCII et le GAMME présent sur l'écran."""
    print(BANNER_LOGO)

# ── Progress spinner state ──
_spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
_spinner_idx    = 0

def render_progress(stage, percent, extra_info=""):
    """
    Loader dynamique clean et élégant sous l'ASCII Art.
    """
    global _spinner_idx

    _spinner_idx = (_spinner_idx + 1) % len(_spinner_frames)
    spinner = _spinner_frames[_spinner_idx]

    bar_width = 28
    filled = int(bar_width * percent // 100)
    bar = "━" * filled + "╌" * (bar_width - filled)

    if percent >= 100:
        color = _GREEN
        spinner = "✓"
    elif percent >= 70:
        color = _CYAN
    elif percent >= 40:
        color = "\033[94m"   # bleu
    else:
        color = _YELLOW

    # Si un chemin long est passé, garder les 55 derniers caractères pour voir le nom de fichier / sous-dossier actuel
    if extra_info:
        if len(extra_info) > 55:
            info_display = "..." + extra_info[-52:]
        else:
            info_display = extra_info
    else:
        info_display = ""

    line = (
        f"\r{color}{spinner}{_RESET} "
        f"{color}[{bar}]{_RESET} "
        f"{_BOLD}{percent:3d}%{_RESET}  "
        f"{_DIM}{stage:<20}{_RESET}  "
        f"\033[37m{info_display:<55}{_RESET}"
    )

    sys.stdout.write(line)
    sys.stdout.flush()

    if percent >= 100:
        sys.stdout.write("\n")

def print_client_completion(scan_id):
    """Affichage final sobre et épuré."""
    sys.stdout.write("\n")
    print(f"  {_GREEN}✓{_RESET}  {_BOLD}Analyse terminée{_RESET}  {_DIM}·{_RESET}  "
          f"\033[96m{scan_id}{_RESET}  {_DIM}· chiffré & transmis{_RESET}")
    sys.stdout.write("\n")

def print_admin_report(scan_data):
    pass
