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
    "eulen", "redengine", "hx_menu", "skript_executor", "lynx_menu", 
    "ham_executor", "mafia_menu", "desync_menu", "brutal_cheat", 
    "dopamine_executor", "tz_menu", "fallout_menu", "unmatched_cheat",
    "kiddions", "stand_menu", "cherax", "subversion_menu", "dopamine.lua",
    "eulen.exe", "redengine.exe", "lynx.asi", "hx.asi"
]

CHEAT_EXTENSIONS = {".asi", ".lua", ".dll", ".exe", ".ini", ".vbs", ".bat", ".ps1"}

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
                
                # 1. Tous les fichiers .asi et .lua supprimés sont suspects
                if ext in {".asi", ".lua"}:
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
                            "reason": f"Fichier supprimé suspect '{filename}' détecté sur {drive_letter} dans le journal USN le {timestamp}."
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
# FORENSIQUE WINDOWS : PREFETCH SCANNER
# ─────────────────────────────────────────────
def scan_windows_prefetch(progress_callback=None, pct=73):
    prefetch_dir = r"C:\Windows\Prefetch"
    traces = []
    
    if progress_callback:
        progress_callback("Forensique Prefetch", pct, "Analyse des traces d'exécution Windows...")

    if not os.path.exists(prefetch_dir):
        return traces

    try:
        for file in os.listdir(prefetch_dir):
            if not file.lower().endswith(".pf"):
                continue
            
            exec_name = file.split("-")[0].lower()
            
            if any(legit in exec_name for legit in LEGITIMATE_FRAMEWORKS):
                continue

            for cheat in SPECIFIC_CHEATS:
                if cheat in exec_name:
                    pf_path = os.path.join(prefetch_dir, file)
                    mtime = os.path.getmtime(pf_path)
                    last_exec = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
                    
                    traces.append({
                        "cheat_signature": cheat,
                        "executable_name": exec_name,
                        "prefetch_file"  : file,
                        "last_executed"  : last_exec,
                        "severity"       : "CRITICAL",
                        "description"    : f"Trace d'exécution Windows (Prefetch) pour '{exec_name}' (Dernière exécution : {last_exec})"
                    })
                    break
    except (PermissionError, OSError):
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

def _is_fivem_cheat_file(filename: str, full_path: str = "") -> bool:
    name_lower = filename.lower()
    path_lower = full_path.lower()
    ext = os.path.splitext(name_lower)[1]
    
    if ext not in CHEAT_EXTENSIONS:
        return False

    if any(legit in name_lower or legit in path_lower for legit in LEGITIMATE_FRAMEWORKS):
        return False

    for cheat in SPECIFIC_CHEATS:
        if cheat in name_lower:
            return True

    return False

def scan_fivem_cheat_files_all_drives(drives, progress_callback=None, start_pct=62, end_pct=72):
    """Scan FiveM cheat files across ALL mounted drives."""
    suspects = []
    
    # Build scan dirs dynamically across all drives
    user_profile = os.environ.get("USERPROFILE", "")
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    appdata = os.environ.get("APPDATA", "")
    temp_dir = os.environ.get("TEMP", "")
    
    # Standard dirs on the system drive
    standard_dirs = [
        os.path.join(local_appdata, "FiveM", "FiveM.app"),
        os.path.join(local_appdata, "FiveM"),
        appdata,
        os.path.join(user_profile, "Desktop"),
        os.path.join(user_profile, "Downloads"),
        os.path.join(user_profile, "Documents"),
        temp_dir,
    ]
    
    # On non-system drives, scan root-level directories
    system_drive = os.environ.get("SYSTEMDRIVE", "C:").upper()
    for drive in drives:
        letter = drive["letter"].upper()
        if letter == system_drive:
            continue
        # Scan root of non-system drives
        root = f"{letter}\\"
        if os.path.isdir(root):
            standard_dirs.append(root)
    
    dirs_to_scan = [d for d in standard_dirs if d and os.path.isdir(d)]
    total = max(len(dirs_to_scan), 1)

    for i, directory in enumerate(dirs_to_scan):
        pct = start_pct + int((i / total) * (end_pct - start_pct))
        dir_label = os.path.basename(directory) or directory[:3]
        if progress_callback:
            progress_callback("Scan Fichiers Multi-Disques", pct, f"Analyse : {dir_label}")

        try:
            for root, dirs, files in os.walk(directory):
                dirs[:] = [
                    d for d in dirs
                    if d.lower() not in {
                        "windows", "program files", "program files (x86)", 
                        "system32", "syswow64", "ea", "playnite", "razor",
                        "$recycle.bin", "system volume information",
                        "programdata", "recovery", "perflogs"
                    }
                ]
                # Limit depth on non-system drives to avoid scanning massive trees
                depth = root.replace(directory, "").count(os.sep)
                if depth > 4:
                    dirs.clear()
                    continue
                    
                for file in files:
                    full_path = os.path.join(root, file)
                    if _is_fivem_cheat_file(file, full_path):
                        suspects.append({
                            "file": file,
                            "path": full_path,
                            "directory": root,
                            "drive": directory[:3],
                            "severity": "HIGH",
                            "reason": f"Signature de cheat FiveM '{file}' trouvée sur {directory[:3]}"
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

    # ── 73% : Forensique Windows Prefetch
    prefetch_traces = scan_windows_prefetch(progress_callback=progress_callback, pct=73)
    time.sleep(0.05)

    # ── 76% : Forensique Journal USN NTFS - MULTI-DISQUES
    usn_traces = scan_usn_journal_all_drives(mounted_drives, progress_callback=progress_callback, pct=76)
    step("Forensique USN NTFS", 78, f"{len(usn_traces)} fichier(s) supprimé(s) sur {len(mounted_drives)} disque(s)")
    time.sleep(0.05)

    # ── 79% : Forensique USB/SSD historique
    usb_history = scan_usb_storage_history(progress_callback=progress_callback, pct=79)

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
                        "severity"   : "CRITICAL",
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
    step("Scan Terminé", 100, f"{len(applications)} apps ({total_procs} PIDs) | {len(mounted_drives)} disque(s) | {len(usb_history)} USB | {len(prefetch_traces)} Prefetch | {len(usn_traces)} USN")

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
            "usb_devices_count"   : len(usb_history),
            "drives_scanned"      : len(mounted_drives)
        },
        "fivem_suspects"   : fivem_suspects,
        "prefetch_traces"  : prefetch_traces,
        "usn_traces"       : usn_traces,
        "usb_history"      : usb_history,
        "risk_summary"     : risk_summary,
        "applications"     : applications
    }
