import sys
import os
import time

SHIELD_ICON = "🛡️ "

# Magnifique ASCII Art "ANTI" 3D turquoise
BANNER_LOGO = f"""\033[96m
================================================================================
   █████╗ ███╗   ██╗████████╗██╗     {SHIELD_ICON} ANTI DEFENSE SYSTEM
  ██╔══██╗████╗  ██║╚══██╔══╝██║     System Integrity & Telemetry Scanner
  ███████║██╔██╗ ██║   ██║   ██║     Version 2.5 (MAJESTIC)
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
    Loader dynamique clean, élégant et fluide (sans saut de ligne intempestif).
    """
    global _spinner_idx

    # S'assurer que le pourcentage commence au moins à 1% pour éviter le sentiment de freeze
    display_pct = max(1, min(100, int(percent)))

    _spinner_idx = (_spinner_idx + 1) % len(_spinner_frames)
    spinner = _spinner_frames[_spinner_idx]

    bar_width = 24
    filled = int(bar_width * display_pct // 100)
    bar = "━" * filled + "╌" * (bar_width - filled)

    if display_pct >= 100:
        color = _GREEN
        spinner = "✓"
    elif display_pct >= 70:
        color = _CYAN
    elif display_pct >= 40:
        color = "\033[94m"   # bleu
    else:
        color = _YELLOW

    # Tronquer proprement l'extra_info pour s'adapter aux petits terminaux CMD/PowerShell sans passer à la ligne
    clean_info = extra_info.replace("\n", " ").replace("\r", "")
    if len(clean_info) > 40:
        info_display = "..." + clean_info[-37:]
    else:
        info_display = clean_info

    # \r\033[K efface entièrement la ligne courante avant de réécrire
    line = (
        f"\r\033[K{color}{spinner}{_RESET} "
        f"{color}[{bar}]{_RESET} "
        f"{_BOLD}{display_pct:3d}%{_RESET}  "
        f"{_DIM}{stage:<16}{_RESET}  "
        f"\033[37m{info_display:<40}{_RESET}"
    )

    sys.stdout.write(line)
    sys.stdout.flush()

    if display_pct >= 100:
        sys.stdout.write("\n")


def print_client_completion(scan_id):
    """Affichage final sobre et épuré."""
    sys.stdout.write("\n")
    print(f"  {_GREEN}✓{_RESET}  {_BOLD}Analyse terminée{_RESET}  {_DIM}·{_RESET}  "
          f"\033[96m{scan_id}{_RESET}  {_DIM}· chiffré & transmis{_RESET}")
    sys.stdout.write("\n")

def print_admin_report(scan_data):
    pass
