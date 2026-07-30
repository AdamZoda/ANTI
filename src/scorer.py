import os

def classify_path(exe_path):
    if not exe_path:
        return "UNKNOWN"
    path_lower = exe_path.lower()
    
    if any(p in path_lower for p in [r"c:\windows\system32", r"c:\windows\syswow64", r"c:\program files", r"c:\program files (x86)"]):
        return "SYSTEM_STANDARD"
    elif any(p in path_lower for p in [r"appdata\local\programs", r"appdata\local\microsoft", r"appdata\roaming\npm"]):
        return "USER_PROGRAM_STANDARD"
    elif any(p in path_lower for p in [r"\temp\\", r"appdata\local\temp", r"c:\users\public", r"c:\programdata\temp"]):
        return "SUSPICIOUS_TEMP"
    elif r"appdata" in path_lower:
        return "USER_APPDATA_GENERIC"
    else:
        return "STANDARD_OTHER"

def evaluate_app_risk(app_info):
    """
    Moteur de Scoring Contextuel Avancé (Anti Faux-Positifs).
    Niveaux :
      - OBSERVATION (Score 0 - 15) : Information standard
      - ANOMALIE (Score 16 - 35)    : Comportement peu fréquent
      - SUSPECT (Score 36 - 65)     : Indicateurs de risque significatifs
      - DANGER (Score 66 - 100)     : Anomalies majeures ou usurpation système
    """
    score = 0
    observations = []
    
    exe_path = app_info.get("exe_path") or ""
    path_class = classify_path(exe_path)
    signed = app_info.get("signature", {}).get("signed", False)
    name = (app_info.get("name") or "").lower()

    # 1. Usurpation de Nom Système Majeure (ex: svchost.exe hors de Windows)
    system_critical_names = ["svchost.exe", "lsass.exe", "csrss.exe", "smss.exe", "services.exe", "explorer.exe"]
    if name in system_critical_names:
        if "c:\\windows" not in exe_path.lower():
            score += 70
            observations.append({
                "level": "SUSPECT",
                "severity": "CRITIQUE",
                "title": f"Usurpation de Nom Système ({name})",
                "description": f"Exécution d'un fichier nommé '{name}' en dehors du répertoire officiel C:\\Windows."
            })

    # 2. Analyse de l'emplacement & de la signature
    if path_class == "SUSPICIOUS_TEMP":
        if not signed:
            score += 45
            observations.append({
                "level": "SUSPECT",
                "severity": "ÉLEVÉE",
                "title": "Exécutable Non Signé dans un Dossier Temporaire / Public",
                "description": "Fichier exécutable situé dans %TEMP% ou Public sans signature numérique valide."
            })
        else:
            score += 15
            observations.append({
                "level": "ANOMALIE",
                "severity": "FAIBLE",
                "title": "Exécution depuis un Répertoire Temporaire",
                "description": "Exécutable signé présent dans %TEMP% (possible programme d'installation)."
            })
            
    elif path_class == "USER_PROGRAM_STANDARD":
        if not signed:
            score += 5
            observations.append({
                "level": "OBSERVATION",
                "severity": "INFO",
                "title": "Binaire Non Signé dans un Répertoire Utilisateur Standard",
                "description": "Application installée dans l'espace utilisateur (AppData\\Local\\Programs). Comportement courant pour de nombreux IDE et outils."
            })
        else:
            observations.append({
                "level": "OBSERVATION",
                "severity": "INFO",
                "title": "Application Utilisateur Valide",
                "description": "Fichier signé et situé dans le répertoire d'installation utilisateur."
            })
            
    elif path_class == "SYSTEM_STANDARD":
        sig_status = app_info.get("signature", {}).get("status", "Unknown")
        if not signed and sig_status not in ["Unknown", "Inconclusive"] and "c:\\windows" in exe_path.lower():
            score += 50
            observations.append({
                "level": "SUSPECT",
                "severity": "ÉLEVÉE",
                "title": "Composant Système Sans Signature Valide",
                "description": "Fichier présent dans System32 mais dont la signature est absente ou corrompue."
            })

    final_score = min(100, score)
    
    if final_score >= 60:
        verdict_level = "HIGH_RISK"
    elif final_score >= 30:
        verdict_level = "MEDIUM_RISK"
    else:
        verdict_level = "LOW_RISK"

    return {
        "risk_score": final_score,
        "verdict_level": verdict_level,
        "observations": observations,
        "is_suspicious": final_score >= 35
    }

def calculate_overall_risk_grouped(apps_list, system_info=None):
    """
    Calcule le risque global et le niveau de confiance (Confidence Rating).
    Prend en compte la présence actuelle, les traces historiques (Prefetch)
    et les indices de formatage récent.
    """
    max_score = 0
    suspicious_apps = 0
    total_observations = 0
    has_prefetch_trace = False
    
    for app in apps_list:
        r = app.get("risk_assessment", {})
        score = r.get("risk_score", 0)
        if score > max_score:
            max_score = score
        if r.get("is_suspicious"):
            suspicious_apps += 1
        total_observations += len(r.get("observations", []))
        
        # Vérifier si c'est une trace Prefetch
        if app.get("signature", {}).get("status") == "PrefetchTrace":
            has_prefetch_trace = True

    # ── Évaluation de la Confiance & Détection d'Anti-Forensics (Nettoyage)
    confidence_level = "ÉLEVÉ (HIGH)"
    confidence_score = 95
    confidence_reasons = []

    # 1. Formatage Récent
    if system_info and system_info.get("is_recent_reformat"):
        confidence_level = "FAIBLE (LOW - Formatage Récent)"
        confidence_score = 40
        confidence_reasons.append("Windows a été réinstallé dans les 48 dernières heures (traces historiques limitées).")
        if max_score < 35:
            max_score = 35

    # 2. Nettoyage Manuel de Prefetch (Anti-Forensics Wiping)
    if system_info and system_info.get("is_prefetch_wiped") and not system_info.get("is_recent_reformat"):
        confidence_level = "SUSPECT (NETTOYAGE MANUEL PREFETCH)"
        confidence_score = 30
        pf_count = system_info.get("prefetch_file_count", 0)
        confidence_reasons.append(f"Nettoyage manuel des traces d'exécution détecté ! (Dossier C:\\Windows\\Prefetch purgé : seulement {pf_count} fichiers .pf trouvés).")
        # Augmenter le score de risque global car purger le Prefetch est un comportement typique d'évitement
        if max_score < 65:
            max_score = 65

    # 3. Périphérique USB débranché récemment
    if system_info and system_info.get("has_disconnected_usb"):
        confidence_reasons.append("Un ou plusieurs périphériques de stockage USB / SSD externes ont été déconnectés récemment de la machine.")
        if max_score < 45:
            max_score = 45

    elif has_prefetch_trace:
        confidence_level = "MOYEN-ÉLEVÉ (MEDIUM-HIGH)"
        confidence_score = 80
        confidence_reasons.append("Traces d'exécution historiques (Prefetch) détectées pour des fichiers supprimés.")

    # ── Verdict final
    if max_score >= 60:
        threat_level = "ÉLEVÉ (HIGH)"
        verdict = "CHEATER (Triche Détectée ou Exécutée)"
    elif max_score >= 30:
        threat_level = "MODÉRÉ (MEDIUM)"
        verdict = "ANORMAL (À Inspecter)"
    else:
        threat_level = "FAIBLE (LOW - SÉCURISÉ)"
        verdict = "CLEAN"

    return {
        "overall_risk_score": max_score,
        "threat_level": threat_level,
        "verdict": verdict,
        "confidence_level": confidence_level,
        "confidence_score": confidence_score,
        "confidence_reasons": confidence_reasons,
        "suspicious_applications_count": suspicious_apps,
        "total_applications_count": len(apps_list),
        "total_observations_count": total_observations
    }
