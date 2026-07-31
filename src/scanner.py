import os
import sys
import time
import socket
import getpass
import psutil
import subprocess
import hashlib
import winreg
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from src.authenticode import get_file_sha256, check_authenticode_signature
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
    "mafia", "vanity", "ham",
    
    # Generic names frequently seen in suspicious tools
    "cheat_loader", "cheatloader", "mod_loader", "modloader", "menu_loader", 
    "injector", "injector.exe", "loader.exe", "executor.exe", "external.exe", "internal.exe",

    # Added cheat names & sample signatures (realboss, masqueraded loader, spoty)
    "hammafia", "susano", "tz project", "tzx", "skript", "phaze", "lumia", 
    "keyser", "tiago", "projectyx", "kekhack", "lunacy", "hx hacks", "hx",
    "realboss", "realboss.v4", "spoty.bat", "ejtgv5l1d", "ntoskrnl.exe"
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

KNOWN_CHEAT_HASHES = {
    # Cheat 1 (loader.rar -> ntoskrnl.exe)
    "8e79140f00872ae0c3323e4bef2d797ab0a44a423d842818e3510dad649abce7": "Cheat 1 Sample (ntoskrnl.exe masqueraded loader)",
    "28c698491cf2672f864a68025772e027": "Cheat 1 MD5 Hash",
    # Cheat 2 (realboss.v4.zip -> loader.exe)
    "620890674d5fd3607e26f034b1d4a020956fe1902cb80824293ee4a49f344e0c": "Cheat 2 Sample (realboss.v4.zip -> loader.exe)",
    "8e54a8042b791d5f01cf529f0054c735": "Cheat 2 MD5 Hash"
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
    "playnite", "antigravity", "visual studio", "docker", "node_modules"
]

# ─────────────────────────────────────────────
# DÉTECTION DYNAMIQUE DES DISQUES MONTÉS
# ─────────────────────────────────────────────
def get_all_mounted_drives():
    """Détecte tous les disques/partitions montés (C:, D:, E:, etc.)"""
    drives = []
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
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=15
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
    """Analyse le journal USN de TOUS les disques détectés."""
    if progress_callback:
        progress_callback("Forensique USN NTFS", pct, "Analyse des suppressions récentes sur tous les disques...")
        
    all_deleted = []
    for i, drive in enumerate(drives):
        letter = drive["letter"]
        if drive.get("fstype", "").upper() != "NTFS":
            continue
        if progress_callback:
            sub_pct = pct + int((i / max(len(drives), 1)) * 3)
            progress_callback("Forensique USN NTFS", sub_pct, f"Analyse journal USN : {letter}")
        all_deleted.extend(scan_usn_journal_drive(letter))
    
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
# INFOS SYSTÈME
# ─────────────────────────────────────────────
def get_os_installation_date():
    try:
        ps_cmd = "(Get-CimInstance Win32_OperatingSystem).InstallDate.ToString('yyyy-MM-dd HH:mm:ss')"
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=3
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

def _check_pe_virtualizer_anomaly(file_path: str) -> dict:
    """
    Examine les en-têtes PE d'un exécutable pour détecter des anomalies de virtualisation de code / packer (ex: VMProtect/Themida/Custom Stub).
    Un exécutable dont la section .text a RawSize == 0 avec un binaire non signé est très probablement un loader de cheat obfusqué.
    """
    try:
        if not os.path.isfile(file_path) or os.path.getsize(file_path) < 1024:
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

        for i in range(num_sections):
            start = sec_offset + i * 40
            if start + 40 <= len(header):
                sec_data = header[start : start + 40]
                sec_name = sec_data[:8].rstrip(b'\x00').decode('ascii', errors='ignore').lower()
                virt_size = struct.unpack('<I', sec_data[8:12])[0]
                raw_size = struct.unpack('<I', sec_data[16:20])[0]

                # Section code .text avec RawSize == 0 et VirtSize > 0 (Empreinte de Virtualisation/Packer)
                if sec_name == ".text" and raw_size == 0 and virt_size > 0x10000:
                    return {
                        "is_cheat": True,
                        "severity": "CRITICAL",
                        "reason": f"Anomalie PE / Obfuscation Virtuelle : Section .text virtuelle ({hex(virt_size)}) avec taille disque 0 octet dans '{os.path.basename(file_path)}' (Cheat Stub Obfusqué) !"
                    }
    except Exception:
        pass

    return None

def _is_fivem_cheat_file(filename: str, full_path: str = "") -> dict:
    """
    Vérifie si un fichier est un cheat FiveM ou une usurpation système.
    Retourne un dict {'is_cheat': True, 'reason': '...', 'severity': '...'} ou None.
    """
    name_lower = filename.lower().strip()
    path_lower = full_path.lower().strip()
    ext = os.path.splitext(name_lower)[1]

    # Ignorer les frameworks légitimes
    if any(legit in name_lower or legit in path_lower for legit in LEGITIMATE_FRAMEWORKS):
        return None

    # 1. Usurpation de nom système (System Process Masquerading)
    # Ex: ntoskrnl.exe, svchost.exe dans Downloads, AppData, Documents, etc.
    if name_lower in SYSTEM_PROCESS_NAMES:
        valid_sys_paths = (r"c:\windows\system32", r"c:\windows\syswow64", r"c:\windows\winsxs")
        if full_path and not any(path_lower.startswith(vp) for vp in valid_sys_paths):
            return {
                "is_cheat": True,
                "severity": "CRITICAL",
                "reason": f"Usurpation de Fichier Système (Masquerading) : Fichier '{filename}' trouvé hors du dossier System32 !"
            }

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

        # 3. Contrôle d'Anomalie PE / Virtualisation
        pe_match = _check_pe_virtualizer_anomaly(full_path)
        if pe_match:
            return pe_match

    if ext not in CHEAT_EXTENSIONS:
        return None

    for cheat in SPECIFIC_CHEATS:
        if cheat in name_lower:
            return {
                "is_cheat": True,
                "severity": "CRITICAL" if cheat in ["ntoskrnl.exe", "realboss", "eulen", "redengine"] else "HIGH",
                "reason": f"Signature de cheat FiveM '{cheat}' détectée dans le fichier '{filename}'"
            }

    return None

def _scan_archive_contents(archive_path: str):
    """
    Inspecte l'intérieur des archives (.zip, .rar, .7z) sans les extraire sur disque.
    Retourne la liste des artefacts suspects trouvés à l'intérieur.
    """
    suspects_found = []
    ext = os.path.splitext(archive_path.lower())[1]
    
    if ext == ".zip":
        try:
            import zipfile
            with zipfile.ZipFile(archive_path, 'r') as z:
                for item in z.infolist():
                    fname = item.filename.rstrip()
                    base_name = os.path.basename(fname).lower().strip()
                    if base_name:
                        match = _is_fivem_cheat_file(base_name, fname)
                        if match:
                            suspects_found.append((base_name, fname, match["reason"]))
        except Exception:
            pass
    elif ext in {".rar", ".tar", ".gz"}:
        try:
            import tarfile
            with tarfile.open(archive_path, 'r:*') as t:
                for member in t.getmembers():
                    base_name = os.path.basename(member.name).lower().strip()
                    if base_name:
                        match = _is_fivem_cheat_file(base_name, member.name)
                        if match:
                            suspects_found.append((base_name, member.name, match["reason"]))
        except Exception:
            pass
            
    return suspects_found

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
    """Scan FiveM cheat files across ALL mounted drives — optimisé vitesse."""
    suspects = []

    user_profile = os.environ.get("USERPROFILE", "")
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    appdata = os.environ.get("APPDATA", "")
    temp_dir = os.environ.get("TEMP", "")
    local_temp = os.path.join(local_appdata, "Temp")

    # ── Dossiers prioritaires ciblés (scan rapide et précis)
    standard_dirs = [
        # FiveM : scan limité aux sous-dossiers cheat-suspects uniquement
        os.path.join(local_appdata, "FiveM", "FiveM.app", "plugins"),
        os.path.join(local_appdata, "FiveM", "FiveM.app", "data"),
        os.path.join(local_appdata, "FiveM", "FiveM.app", "crashes"),
        # Utilisateur
        os.path.join(user_profile, "Desktop"),
        os.path.join(user_profile, "Downloads"),
        os.path.join(user_profile, "Documents"),
        os.path.join(user_profile, "Videos"),
        # Temp
        temp_dir,
        local_temp,
        # Fichiers récents Windows (LNK vers fichiers récemment ouverts)
        os.path.join(appdata, "Microsoft", "Windows", "Recent"),
        # AppData racine
        appdata,
        local_appdata,
        # Racine du profil utilisateur (ex: C:\Users\adam\ham\)
        user_profile,
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

    # ── Corbeille Windows ($RECYCLE.BIN) — fichiers supprimés non purgés
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

    total = max(len(dirs_to_scan), 1)

    # Profondeur max par type de dossier
    DEPTH_LIMITS = {
        "fivem.app": 2,     # FiveM limité à 2 niveaux (plugins/, data/)
        "recent": 1,        # Fichiers récents = plat
        "recycle.bin": 1,   # Corbeille = plat
        "roaming": 3,
        "localappdata": 3,
        "users": 2,         # Racine profil utilisateur
    }

    def _get_depth_limit(directory: str) -> int:
        d_lower = directory.lower()
        if "fivem.app" in d_lower:
            return 2
        if "recent" in d_lower:
            return 1
        if "$recycle.bin" in d_lower:
            return 1
        if "localappdata" in d_lower or "local\\temp" in d_lower:
            return 3
        if "roaming" in d_lower:
            return 3
        return 4   # Défaut général

    for i, directory in enumerate(dirs_to_scan):
        pct = start_pct + int((i / total) * (end_pct - start_pct))
        dir_label = os.path.basename(directory) or directory[:3]
        if progress_callback:
            progress_callback("Scan Fichiers Multi-Disques", pct, f"Analyse : {dir_label}")

        depth_limit = _get_depth_limit(directory)
        is_recent_dir = "recent" in directory.lower()

        try:
            for root, dirs, files in os.walk(directory):
                depth = root.replace(directory, "").count(os.sep)

                # ── Noms de dossiers suspects
                for d in dirs:
                    d_lower = d.lower().strip()

                    # 1. Noms suspects génériques (ham, 420, cheat, etc.)
                    if d_lower in SUSPICIOUS_FOLDER_NAMES:
                        suspects.append({
                            "file": d,
                            "path": os.path.join(root, d),
                            "directory": root,
                            "drive": directory[:3],
                            "severity": "HIGH",
                            "reason": f"Dossier au nom suspect de cheat/grief détecté : '{d}'"
                        })
                        continue

                    # 2. Correspondance avec signatures de cheats connus
                    for cheat in SPECIFIC_CHEATS:
                        is_match = (cheat == d_lower) or (len(cheat) > 3 and cheat in d_lower)
                        if is_match:
                            suspects.append({
                                "file": d,
                                "path": os.path.join(root, d),
                                "directory": root,
                                "drive": directory[:3],
                                "severity": "HIGH",
                                "reason": f"Dossier suspect lié à un cheat FiveM détecté : '{d}'"
                            })
                            break

                # Limiter les sous-dossiers traversés
                dirs[:] = [
                    d for d in dirs
                    if d.lower() not in {
                        "windows", "program files", "program files (x86)",
                        "system32", "syswow64", "ea", "playnite", "razor",
                        "system volume information", "programdata",
                        "recovery", "perflogs", "winsxs", "servicing"
                    }
                ]

                if depth >= depth_limit:
                    dirs.clear()
                    continue

                # Compteur pour rafraîchir le callback en temps réel sans ralentir la boucle
                file_count = 0
                for file in files:
                    file_count += 1
                    full_path = os.path.join(root, file)
                    file_lower = file.lower()
                    ext = os.path.splitext(file_lower)[1]

                    if progress_callback and file_count % 30 == 0:
                        progress_callback("Scan Fichiers", pct, f"{file}")

                    # ── Fichiers Recent (.lnk) : extraire la cible du raccourci
                    if is_recent_dir and ext == ".lnk":
                        try:
                            # Lire la cible du fichier LNK (offset fixe 76)
                            with open(full_path, "rb") as lf:
                                lnk_data = lf.read(4096)
                            # Chercher un chemin Windows dans les données brutes
                            import re as _re
                            targets = _re.findall(b'[A-Za-z]:\\\\[^\x00\r\n"]{5,120}', lnk_data)
                            for t in targets:
                                t_str = t.decode("utf-8", errors="ignore")
                                t_lower = t_str.lower()
                                t_base = os.path.basename(t_str)
                                lnk_match = _is_fivem_cheat_file(t_base, t_str)
                                if lnk_match:
                                    suspects.append({
                                        "file": file,
                                        "path": full_path,
                                        "directory": root,
                                        "drive": directory[:3],
                                        "severity": "CRITICAL",
                                        "reason": f"Raccourci Recent '{file}' pointe vers un cheat : '{t_str}'"
                                    })
                                    break
                        except Exception:
                            pass
                        continue

                    # ── Vérification directe du fichier
                    match = _is_fivem_cheat_file(file, full_path)
                    if match:
                        suspects.append({
                            "file": file,
                            "path": full_path,
                            "directory": root,
                            "drive": directory[:3],
                            "severity": match.get("severity", "HIGH"),
                            "reason": match.get("reason", f"Signature suspecte '{file}' sur {directory[:3]}")
                        })

                    # ── Inspection du contenu des archives (.zip, .rar, .7z)
                    elif ext in ARCHIVE_EXTENSIONS:
                        archive_suspects = _scan_archive_contents(full_path)
                        for fname, inner_path, reason in archive_suspects:
                            suspects.append({
                                "file": file,
                                "path": full_path,
                                "directory": root,
                                "drive": directory[:3],
                                "severity": "CRITICAL",
                                "reason": f"Archive suspecte '{file}' contenant le fichier de cheat '{fname}' ({inner_path})"
                            })

        except (PermissionError, OSError):
            pass

    return suspects


def get_hardware_id():
    try:
        ps_cmd = "(Get-CimInstance Win32_ComputerSystemProduct).UUID"
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=3
        )
        uuid_str = res.stdout.strip()
        if uuid_str and len(uuid_str) > 10 and "error" not in uuid_str.lower():
            h = hashlib.sha256(uuid_str.encode()).hexdigest().upper()
            return f"HWID-{h[:4]}-{h[4:8]}-{h[8:12]}"
    except Exception:
        pass
    raw = f"{socket.gethostname()}_{psutil.cpu_count()}_{round(psutil.virtual_memory().total / (1024**3))}"
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

def get_extended_system_info():
    info = {}
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "(Get-CimInstance Win32_OperatingSystem).Caption"],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=3
        )
        info["os_version"] = res.stdout.strip() or "Windows"
    except Exception:
        info["os_version"] = "Windows"

    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "(Get-CimInstance Win32_VideoController).Name | Select -First 1"],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=3
        )
        info["gpu"] = res.stdout.strip() or "N/A"
    except Exception:
        info["gpu"] = "N/A"

    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "(Get-CimInstance Win32_Processor).Name | Select -First 1"],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=3
        )
        info["cpu_name"] = res.stdout.strip() or "N/A"
    except Exception:
        info["cpu_name"] = "N/A"

    try:
        info["local_ip"] = socket.gethostbyname(socket.gethostname())
    except Exception:
        info["local_ip"] = "N/A"

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

    return info

def process_single(pinfo):
    try:
        pid  = pinfo['pid']
        name = pinfo['name'] or f"PID_{pid}"
        exe  = pinfo['exe']
        dll_count = 0
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

def run_system_scan(progress_callback=None):

    def step(stage, pct, info=""):
        if progress_callback:
            progress_callback(stage, pct, info)

    # ── 5% : HWID
    hwid = get_hardware_id()
    step("Initialisation", 5, f"HWID : {hwid}")
    time.sleep(0.05)

    # ── 10% : Détection des disques montés
    step("Détection Disques", 10, "Détection de toutes les unités de stockage...")
    mounted_drives = get_all_mounted_drives()
    drive_labels = ", ".join([f"{d['letter']} ({d['fstype']} {d['total_gb']}GB)" for d in mounted_drives])
    step("Détection Disques", 12, f"{len(mounted_drives)} disque(s) : {drive_labels}")
    time.sleep(0.05)

    # ── 15% : Infos système & Date Installation OS
    step("Infos Système", 15, "Collecte CPU / GPU / Date Installation OS...")
    ext_info = get_extended_system_info()
    os_install = get_os_installation_date()
    time.sleep(0.05)

    system_info = {
        "hwid"            : hwid,
        "hostname"        : socket.gethostname(),
        "user"            : getpass.getuser(),
        "local_ip"        : ext_info.get("local_ip", "N/A"),
        "platform"        : sys.platform,
        "os_version"      : ext_info.get("os_version", "Windows"),
        "cpu_name"        : ext_info.get("cpu_name", "N/A"),
        "cpu_count"       : psutil.cpu_count(logical=True),
        "gpu"             : ext_info.get("gpu", "N/A"),
        "ram_gb"          : round(psutil.virtual_memory().total / (1024**3), 1),
        "disk_total_gb"   : ext_info.get("disk_total_gb", 0),
        "disk_used_pct"   : ext_info.get("disk_used_pct", 0),
        "uptime"          : ext_info.get("uptime", "N/A"),
        "os_install_date" : os_install["install_date"],
        "os_age_hours"    : os_install["age_hours"],
        "reformat_traces" : os_install["status_text"],
        "is_recent_reformat": os_install["is_recent_reformat"],
        "mounted_drives"  : mounted_drives
    }

    # ── 25% : Disque
    step("Disque & Performance", 25, "Mesure de la vitesse de lecture...")
    disk_speed = measure_disk_read_speed()
    step("Disque & Performance", 30, f"Disque : {disk_speed} MB/s")
    time.sleep(0.05)

    # ── 38% : RAM
    ram_usage = psutil.virtual_memory().percent
    step("Mémoire RAM", 38, f"Allocation RAM : {ram_usage}%")
    time.sleep(0.05)

    # ── 45% : Processus
    all_procs = [p.info for p in psutil.process_iter(['pid', 'name', 'exe', 'username'])]
    total_procs = len(all_procs)
    step("Processus & DLLs", 45, f"Analyse de {total_procs} processus en parallèle...")

    raw_processes  = []
    total_dlls     = 0
    with ThreadPoolExecutor(max_workers=16) as ex:
        for res in ex.map(process_single, all_procs):
            if res:
                raw_processes.append(res)
                total_dlls += res.get("loaded_dll_count", 0)

    step("Processus & DLLs", 55, f"{len(raw_processes)} processus analysés | {total_dlls} DLLs")
    time.sleep(0.05)

    # ── 58% : Boot Time
    try:
        boot_ts = psutil.boot_time()
        boot_dt = datetime.fromtimestamp(boot_ts)
        boot_time_str = boot_dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        boot_time_str = "Inconnu"
    system_info["boot_time"] = boot_time_str

    # ── 62-72% : Scan fichiers FiveM MULTI-DISQUES
    fivem_suspects = scan_fivem_cheat_files_all_drives(
        drives=mounted_drives,
        progress_callback=progress_callback,
        start_pct=62,
        end_pct=72
    )

    # ── 73% : Forensique Windows Prefetch & Wiping Detection
    prefetch_res = scan_windows_prefetch(progress_callback=progress_callback, pct=73)
    prefetch_traces = prefetch_res.get("traces", [])
    system_info["prefetch_file_count"] = prefetch_res.get("total_pf_count", 0)
    system_info["is_prefetch_wiped"] = prefetch_res.get("is_wiped", False)
    time.sleep(0.05)

    # ── 74% : Forensique Détections Windows Defender
    defender_traces = scan_windows_defender_threats(progress_callback=progress_callback, pct=74)
    time.sleep(0.05)

    # ── 76% : Forensique Journal USN NTFS - MULTI-DISQUES
    usn_traces = scan_usn_journal_all_drives(mounted_drives, progress_callback=progress_callback, pct=76)
    step("Forensique USN NTFS", 78, f"{len(usn_traces)} fichier(s) supprimé(s) sur {len(mounted_drives)} disque(s)")
    time.sleep(0.05)

    # ── 79% : Forensique USB/SSD historique
    usb_history = scan_usb_storage_history(progress_callback=progress_callback, pct=79)
    disconnected_usbs = [u for u in usb_history if not u.get("is_connected")]
    system_info["has_disconnected_usb"] = len(disconnected_usbs) > 0
    system_info["disconnected_usb_count"] = len(disconnected_usbs)

    # ── 82% : Regroupement
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

    # ── 85-95% : Scoring par application
    apps_list    = list(grouped_map.items())
    total_apps   = max(len(apps_list), 1)
    applications = []

    for idx, ((name, exe), app_data) in enumerate(apps_list):
        pct = 85 + int((idx / total_apps) * 10)
        if progress_callback and idx % 20 == 0:
            progress_callback("Calcul du Risque", pct, f"Scoring {idx+1}/{total_apps} applications...")

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
        applications.append(app_item)

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
                    "risk_score"  : 85,
                    "observations": [{
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
                    "risk_score"  : 90,
                    "observations": [{
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
                    "risk_score"  : 95,
                    "observations": [{
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
                    "risk_score"  : 95,
                    "observations": [{
                        "severity"   : "CRITICAL",
                        "title"      : "Fichier Supprimé Détecté dans le Journal NTFS (USN)",
                        "description": trace["reason"]
                    }]
                }
            })

    # ── Risque Global & Confiance
    risk_summary = calculate_overall_risk_grouped(applications, system_info=system_info)

    # ── 100% : Terminé
    step("Scan Terminé", 100, f"{len(applications)} apps ({total_procs} PIDs) | {len(mounted_drives)} disque(s) | {len(usb_history)} USB | {len(prefetch_traces)} Prefetch | {len(usn_traces)} USN | {len(defender_traces)} Defender")

    return {
        "timestamp"        : time.strftime("%Y-%m-%d %H:%M:%S"),
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
            "usb_devices_count"   : len(usb_history),
            "drives_scanned"      : len(mounted_drives)
        },
        "fivem_suspects"   : fivem_suspects,
        "prefetch_traces"  : prefetch_traces,
        "usn_traces"       : usn_traces,
        "defender_traces"  : defender_traces,
        "usb_history"      : usb_history,
        "risk_summary"     : risk_summary,
        "applications"     : applications
    }
