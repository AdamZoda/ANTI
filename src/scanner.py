import os
import sys
import time
import socket
import getpass
import psutil
import subprocess
import hashlib
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from src.authenticode import get_file_sha256, check_authenticode_signature
from src.scorer import evaluate_app_risk, calculate_overall_risk_grouped

# ─────────────────────────────────────────────
# FIVEM CHEAT SIGNATURES & EXTENSIONS
# ─────────────────────────────────────────────
KNOWN_CHEATS = [
    "eulen", "redengine", "hx", "skript", "lynx", "ham", "mafia",
    "desync", "brutal", "dopamine", "watermark", "executor",
    "dumper", "bypass", "tz_menu", "fallout", "absolute", "unmatched",
    "inject", "cheat", "hack", "trainer", "mod_menu", "lua_inject",
    "spoofer", "hwid_spoof", "kiddions", "stand_", "cherax"
]
CHEAT_EXTENSIONS = {".asi", ".lua", ".dll", ".exe", ".ini", ".vbs", ".bat", ".ps1", ".bin"}

FIVEM_SCAN_DIRS = [
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "FiveM", "FiveM.app"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "FiveM"),
    os.environ.get("APPDATA", ""),
    os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"),
    os.path.join(os.environ.get("USERPROFILE", ""), "Downloads"),
    os.path.join(os.environ.get("USERPROFILE", ""), "Documents"),
    os.path.join(os.environ.get("TEMP", ""), ""),
]

# ─────────────────────────────────────────────
# FORENSIQUE WINDOWS : PREFETCH SCANNER
# ─────────────────────────────────────────────
def scan_windows_prefetch(progress_callback=None, pct=75):
    """
    Analyse le dossier C:\\Windows\\Prefetch pour détecter les traces d'exécution
    de programmes supprimés avant le scan (ex: EULEN.EXE-XXXXXX.pf).
    """
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
            
            # Nom du programme dans le fichier prefetch (ex: EULEN.EXE-1234ABCD.pf -> EULEN.EXE)
            exec_name = file.split("-")[0].lower()
            
            for cheat in KNOWN_CHEATS:
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
                        "description"    : f"Trace d'exécution Windows (Prefetch) trouvée pour '{exec_name}' (Dernière exécution : {last_exec})"
                    })
                    break
    except (PermissionError, OSError):
        pass

    return traces

# ─────────────────────────────────────────────
# DÉTECTION DU FORMATAGE (DATE INSTALLATION OS)
# ─────────────────────────────────────────────
def get_os_installation_date():
    """
    Récupère la date d'installation initiale de Windows via le registre.
    Permet de savoir si le PC a été formaté récemment.
    """
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

def _is_fivem_cheat_file(filename: str) -> bool:
    name = filename.lower()
    ext = os.path.splitext(name)[1]
    if ext not in CHEAT_EXTENSIONS:
        return False
    return any(cheat in name for cheat in KNOWN_CHEATS)

def scan_fivem_cheat_files(progress_callback=None, start_pct=65, end_pct=72):
    suspects = []
    dirs_to_scan = [d for d in FIVEM_SCAN_DIRS if d and os.path.isdir(d)]
    total = max(len(dirs_to_scan), 1)

    for i, directory in enumerate(dirs_to_scan):
        pct = start_pct + int((i / total) * (end_pct - start_pct))
        if progress_callback:
            progress_callback("Scan Fichiers FiveM", pct, f"Analyse : {os.path.basename(directory)}")

        try:
            for root, dirs, files in os.walk(directory):
                dirs[:] = [
                    d for d in dirs
                    if d.lower() not in {"windows", "program files", "program files (x86)", "system32", "syswow64"}
                ]
                for file in files:
                    if _is_fivem_cheat_file(file):
                        full_path = os.path.join(root, file)
                        suspects.append({
                            "file": file,
                            "path": full_path,
                            "directory": root,
                            "severity": "HIGH",
                            "reason": f"Signature cheat connue dans '{file}'"
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
        "is_recent_reformat": os_install["is_recent_reformat"]
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

    # ── 50% : Processus
    all_procs = [p.info for p in psutil.process_iter(['pid', 'name', 'exe', 'username'])]
    total_procs = len(all_procs)
    step("Processus & DLLs", 50, f"Analyse de {total_procs} processus en parallèle...")

    raw_processes  = []
    total_dlls     = 0
    with ThreadPoolExecutor(max_workers=16) as ex:
        for res in ex.map(process_single, all_procs):
            if res:
                raw_processes.append(res)
                total_dlls += res.get("loaded_dll_count", 0)

    step("Processus & DLLs", 60, f"{len(raw_processes)} processus analysés | {total_dlls} DLLs")
    time.sleep(0.05)

    # ── 65-72% : Scan fichiers FiveM
    fivem_suspects = scan_fivem_cheat_files(
        progress_callback=progress_callback,
        start_pct=65,
        end_pct=72
    )

    # ── 75% : Forensique Windows Prefetch (Traces d'exécution historiques)
    prefetch_traces = scan_windows_prefetch(progress_callback=progress_callback, pct=75)
    step("Forensique Prefetch", 78, f"{len(prefetch_traces)} trace(s) d'exécution historique(s)")
    time.sleep(0.05)

    # ── 80% : Regroupement
    step("Regroupement Apps", 80, "Regroupement des sous-processus par Application...")
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
            "total_dll_count" : app_data["loaded_dll_count"]
        }
        app_item["risk_assessment"] = evaluate_app_risk(app_item)
        applications.append(app_item)

    # Ajouter les fichiers physiques suspects FiveM
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
                "risk_assessment" : {
                    "risk_score"  : 90,
                    "observations": [{
                        "severity"   : "CRITICAL",
                        "title"      : "Fichier Cheat FiveM Détecté",
                        "description": suspect["reason"]
                    }]
                }
            })

    # Ajouter les traces forensiques Prefetch (Programme exécuté puis supprimé)
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
                "risk_assessment" : {
                    "risk_score"  : 85,
                    "observations": [{
                        "severity"   : "CRITICAL",
                        "title"      : "Trace Historique d'Exécution (Prefetch)",
                        "description": trace["description"]
                    }]
                }
            })

    # ── Risque Global & Confiance
    risk_summary = calculate_overall_risk_grouped(applications, system_info=system_info)

    # ── 100% : Terminé
    step("Scan Terminé", 100, f"{len(applications)} apps ({total_procs} PIDs) | {len(prefetch_traces)} trace(s) Prefetch")

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
        },
        "fivem_suspects"   : fivem_suspects,
        "prefetch_traces"  : prefetch_traces,
        "risk_summary"     : risk_summary,
        "applications"     : applications
    }
