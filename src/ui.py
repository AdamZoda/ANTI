import sys
import time

SHIELD_ICON = "🛡️ "

BANNER_LOGO = f"""
================================================================================
   █████╗ ███╗   ██╗████████╗██╗     {SHIELD_ICON} ANTI DEFENSE SYSTEM
  ██╔══██╗████╗  ██║╚══██╔══╝██║     System Integrity & Telemetry Scanner
  ███████║██╔██╗ ██║   ██║   ██║     Version 1.1 (Contextual Engine)
  ██╔══██║██║╚██╗██║   ██║   ██║     100% Defensive Security Engine
  ██║  ██║██║ ╚████║   ██║   ██║
  ╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝   ╚═╝
================================================================================
"""

def print_banner():
    print("\033[96m" + BANNER_LOGO + "\033[0m")

def render_progress(stage, percent, extra_info=""):
    bar_length = 30
    filled_length = int(bar_length * percent // 100)
    bar = "█" * filled_length + "░" * (bar_length - filled_length)
    
    color = "\033[93m" if percent < 100 else "\033[92m"
    reset = "\033[0m"
    
    sys.stdout.write(f"\r{color}[{percent:3d}%] [{bar}]{reset} | \033[1m{stage:<22}\033[0m | {extra_info:<40}")
    sys.stdout.flush()
    if percent >= 100:
        sys.stdout.write("\n")

def print_client_completion(scan_id):
    print("\n" + "="*80)
    print(f"\033[92m{SHIELD_ICON} SCAN SYSTÈME TERMINÉ AVEC SUCCÈS !\033[0m")
    print("="*80)
    print(f"  ► Identifiant de Scan Unique : \033[1m\033[93m{scan_id}\033[0m")
    print("  ► Statut du Scan             : Transmis et synchronisé avec l'API Web")
    print("  ► Niveau d'Accès Client      : Masqué (Résultats réservés à l'Administrateur)")
    print("="*80)
    print("\033[90mLe rapport d'analyse a été chiffré et envoyé vers votre serveur de sécurité.\033[0m\n")

def print_admin_report(scan_data):
    print("\n" + "="*80)
    print(f"\033[93m{SHIELD_ICON} RAPPORT ADMINISTRATEUR DÉTAILLÉ - SCAN ID: {scan_data.get('scan_id')}\033[0m")
    print("="*80)
    
    sys_info = scan_data.get("system_info", {})
    stats = scan_data.get("stats", {})
    risk = scan_data.get("risk_summary", {})
    disk = scan_data.get("disk_performance", {})

    print(f"Hôte: {sys_info.get('hostname')} | Util: {sys_info.get('user')} | Horodatage: {scan_data.get('timestamp')}")
    print(f"RAM Totale: {sys_info.get('ram_gb')} GB | Vitesse Disque: {disk.get('read_speed_mb_s')} MB/s")
    print(f"Applications: {stats.get('applications_count')} ({stats.get('processes_scanned')} PIDs) | DLLs: {stats.get('total_dlls_scanned')}")
    print("-" * 80)
    
    score = risk.get("overall_risk_score", 0)
    threat = risk.get("threat_level", "INCONNU")
    
    if score >= 60:
        color = "\033[91m"  # Rouge
    elif score >= 30:
        color = "\033[93m"  # Jaune
    else:
        color = "\033[92m"  # Vert
        
    print(f"SCORE DE RISQUE GLOBAL : {color}{score}/100 ({threat})\033[0m")
    print(f"Applications Suspectes : {risk.get('suspicious_applications_count')}")
    print(f"Observations Totales   : {risk.get('total_observations_count')}")
    print("="*80)

    apps = scan_data.get("applications", [])
    suspicious = [a for a in apps if a.get("risk_assessment", {}).get("risk_score", 0) >= 30]
    
    if suspicious:
        print("\n\033[91m[!] APPLICATIONS SUSPECTES DÉTECTÉES :\033[0m")
        for a in suspicious:
            r = a.get("risk_assessment", {})
            sig = a.get("signature", {})
            sig_txt = "Signé" if sig.get("signed") else "NON SIGNÉ"
            pids_str = ", ".join(str(p) for p in a.get("pids", [])[:5])
            if len(a.get("pids", [])) > 5:
                pids_str += "..."
            print(f"  • \033[1m{a.get('app_name')}\033[0m (Score: {r.get('risk_score')}) | {a.get('instances_count')} Instances (PIDs: {pids_str})")
            print(f"    Chemin: {a.get('exe_path')}")
            for obs in r.get("observations", []):
                print(f"    └─ [{obs.get('severity')}] {obs.get('title')} : {obs.get('description')}")
            print()
    else:
        print("\n\033[92m[✓] Aucune application suspecte détectée sur la machine.\033[0m\n")
