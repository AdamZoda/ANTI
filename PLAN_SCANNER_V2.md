# ANTI PC Checker V2 — Plan Complet

## Vision
Créer un **vrai PC checker forensique** capable de détecter les cheats FiveM même si :
- Les fichiers sont supprimés
- Les noms sont renommés
- Les cheats sont packés/obfusqués
- Les cheats utilisent l'injection mémoire

---

## PHASE 1 : Scan Binaire PE Profond (PRIORITÉ HAUTE)

### 1.1 Analyse des Imports PE (Import Address Table)
**Technologie** : `pefile` library (Python)
**Principe** : Chaque exe/DLL a une table d'imports qui montre quelles fonctions Windows il utilise

```python
# APIs dangereuses = signatures de cheats
DANGEROUS_APIS = {
    # Injection mémoire
    "VirtualAllocEx": 80,      # Allouer mémoire dans un processus externe
    "WriteProcessMemory": 90,  # Écrire du code dans un processus
    "CreateRemoteThread": 95,  # Créer un thread dans un processus
    "NtCreateThreadEx": 95,    # Alternative NT à CreateRemoteThread
    "QueueUserAPC": 70,        # Injection APC
    
    # Hooking
    "SetWindowsHookExA": 60,   # Hook de clavier/souris
    "SetWindowsHookExW": 60,   # Hook de clavier/souris (Unicode)
    "UnhookWindowsHookEx": 40, # Désactiver hooks Windows
    
    # Mémoire
    "VirtualProtect": 50,      # Changer les permissions mémoire
    "VirtualProtectEx": 70,    # Changer permissions dans processus externe
    "VirtualAlloc": 30,        # Allocation mémoire (normal si dans le même process)
    
    # Capture d'écran / Overlay
    "GetDC": 20,               # Capture d'écran
    "BitBlt": 30,              # Copie d'écran (ESP/Wallhack)
    "CreateCompatibleDC": 20,  # Double buffer pour overlay
    "StretchBlt": 30,          # Copie d'écran
    
    # Lecture mémoire externe
    "ReadProcessMemory": 80,   # Lire la mémoire d'un autre processus (ESP)
    "OpenProcess": 60,         # Ouvrir un processus externe
    
    # Anti-détection
    "IsDebuggerPresent": 30,   # Détection de debug
    "CheckRemoteDebuggerPresent": 40, # Détection debug avancée
    "NtQueryInformationProcess": 50,  # Anti-debug NT
    
    # Keylog / Input
    "GetAsyncKeyState": 40,    # Lecture des touches (triggerbot)
    "GetKeyState": 30,         # Lecture des touches
    "GetRawInputData": 30,     # Input brut
    
    # Registry
    "RegSetValueExA": 20,      # Écriture registry (persistence)
    "RegSetValueExW": 20,      # Écriture registry (persistence)
}
```

**Score** : Somme des scores des APIs importées (max 100)

### 1.2 Analyse des Sections PE
```python
SECTION_ANALYSIS = {
    "code_cave": {           # Espace vide dans les sections
        "description": "Sections avec beaucoup de zeros (code cave pour injection)",
        "threshold": 0.3,    # > 30% de zeros = suspect
        "score": 70
    },
    "writable_code": {       # Section .text modifiable
        "description": "Section code qui est writable (injection possible)",
        "score": 80
    },
    "high_entropy": {        # Section à haute entropie
        "description": "Section packée/chiffrée",
        "entropy_min": 7.0,
        "score": 60
    },
    "suspicious_names": {    # Noms de sections suspects
        "names": [".packed", ".aspack", ".adata", ".nsp0", ".nsp1", 
                  "MEW", "MPRESS", "vmp", ".vmp0", ".vmp1"],
        "score": 85
    },
    "overlay": {             # Données après la fin du PE
        "description": "Overlay = données ajoutées après le PE (dropper)",
        "score": 60
    }
}
```

### 1.3 Détection de Packers/Obfuscateurs
```python
PACKER_SIGNATURES = {
    # Packer         | Signature dans le binaire
    "VMProtect":     [b"vmp0", b"vmp1", b"VMProtect", b".vmp"],
    "Themida":       [b".themida", b"Oreans", b"Code Virtualizer"],
    "UPX":           [b"UPX0", b"UPX1", b"UPX!"],
    "ASPack":        [b".aspack", b"ASPack"],
    "MPRESS":        [b"MPRESS1", b"MPRESS2"],
    "PECompact":     [b"PEC2", b"pec2", b"PECompact"],
    "Enigma":        [b"Enigma", b".enigma"],
    "Armadillo":     [b"Armadillo", b"nanomite"],
    "Custom":        [b"protect", b"encrypt", b"obfusc", b"scramble"],
}
```

### 1.4 Analyse de Strings Binaire Profonde
```python
CHEAT_STRINGS = {
    # URLs de distribution de cheats
    "cheat_urls": [
        b"discord.gg/", b"discord.com/invite/",
        b"gta5mods.com", b"fivem.net",
        b"unknowncheats.me", b"mpgh.net",
        b"cheathappens.com", b"gamecopyworld.com",
    ],
    # Noms de cheats dans le binaire
    "cheat_names": [
        b"NitWit", b"Eulen", b"RedEngine", b"Stand Menu",
        b"Kiddion", b"Cherax", b"2Take1", b"Impulse",
        b"Ozark", b"Luna Menu", b"Dopamine", b"HamMafia",
        b"PhantomX", b"Menyoo", b"Fallout",
    ],
    # Mots-clés de technique
    "technique_words": [
        b"aimbot", b"wallhack", b"esp", b"triggerbot",
        b"bypass", b"inject", b"hook", b"overlay",
        b"streamproof", b"spoof", b"hwid",
        b"cheat", b"mod menu", b"lua executor",
    ],
    # FiveM specific
    "fivem_specific": [
        b"FiveM", b"cfx.re", b"citizenfx",
        b"lua_executor", b"js_executor",
        b"skript_executor",
    ]
}
```

---

## PHASE 2 : Scan Mémoire en Temps Réel (PRIORITÉ HAUTE)

### 2.1 Détection d'Injection DLL
```python
INJECTION_INDICATORS = {
    # Processus avec DLL injectée
    "suspicious_dll_locations": [
        "\\AppData\\Local\\Temp\\",
        "\\AppData\\Roaming\\",
        "\\ProgramData\\",
        "\\Windows\\Temp\\",
    ],
    # DLL sans signature
    "unsigned_dlls": True,
    # DLL avec haute entropie
    "high_entropy_dlls": True,
    # DLL chargée hors du dossier du processus
    "dll_outside_process_dir": True,
}
```

### 2.2 Détection Process Hollowing
```python
HOLLOWING_INDICATORS = {
    # Processus légitime avec mémoire modifiée
    "modified_sections": True,
    # Thread débutant à une adresse suspecte
    "remote_threads": True,
    # Processus avec peu de DLL mais beaucoup de code
    "few_dlls_much_code": True,
}
```

### 2.3 Scan des Processus Actifs
```python
PROCESS_SCAN = {
    # Vérifier chaque processus
    "checks": [
        "authenticode_signature",    # Signé Microsoft ? OK
        "loaded_dlls",               # DLL chargées
        "memory_regions",            # Régions mémoire
        "threads",                   # Threads actifs
        "handles",                   # Handles ouverts
        "command_line",              # Ligne de commande
        "parent_process",            # Processus parent
        "creation_time",             # Heure de création
    ],
    # Processus légitimes à ignorer
    "legitimate_processes": [
        "dwm.exe", "csrss.exe", "lsass.exe", "svchost.exe",
        "explorer.exe", "taskhostw.exe", "conhost.exe",
        "ShellExperienceHost.exe", "SearchUI.exe",
    ]
}
```

---

## PHASE 3 : Forensique Avancée (PRIORITÉ MOYENNE)

### 3.1 Analyse NTFS Avancée
```python
NTFS_FORENSICS = {
    # MFT (Master File Table)
    "mft_analysis": True,         # Fichiers supprimés mais encore dans MFT
    "mft_timestamps": True,       # Vrai vs faux timestamps
    
    # USN Journal
    "usn_journal": True,          # Historique de modifications
    
    # Alternate Data Streams
    "ads_detection": True,        # Fichiers cachés dans les streams
    
    # EFS (Encrypting File System)
    "efs_detection": True,        # Fichiers chiffrés
}
```

### 3.2 Analyse Registre Avancée
```python
REGISTRY_FORENSICS = {
    # Startup persistence
    "run_keys": [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce",
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunServices",
    ],
    # Uninstall tracking
    "uninstall_keys": True,
    # AppInit_DLLs (injection globale)
    "appinit_dlls": True,
    # Image File Execution Options (debugger hijack)
    "ifeo_debugger": True,
    # Winlogon notification packages
    "winlogon_notify": True,
    # Services
    "services": True,
    # Scheduled tasks
    "scheduled_tasks": True,
}
```

### 3.3 Analyse Réseau
```python
NETWORK_FORENSICS = {
    # Connexions actives
    "active_connections": True,
    # DNS cache
    "dns_cache": True,
    # hosts file
    "hosts_file": True,
    # Firewall rules
    "firewall_rules": True,
    # Proxy settings
    "proxy_settings": True,
}
```

### 3.4 Analyse USB/Hardware
```python
HARDWARE_FORENSICS = {
    # USB device history
    "usb_history": True,
    # Disk serial numbers
    "disk_serials": True,
    # MAC addresses
    "mac_addresses": True,
    # Hardware ID spoofing detection
    "hwid_spoofing": True,
}
```

---

## PHASE 4 : Intelligence Artificielle (PRIORITÉ BASSE)

### 4.1 Machine Learning sur les Fichiers
```python
ML_DETECTION = {
    # Features pour le modèle
    "features": [
        "file_entropy",
        "section_count",
        "import_count",
        "dangerous_api_count",
        "string_count",
        "file_size",
        "compile_time",
        "debug_info_present",
        "signature_present",
        "packer_detected",
    ],
    # Modèle
    "model": "RandomForest",  # ou "XGBoost", "NeuralNetwork"
    "training_data": "known_cheats_vs_legitimate",
}
```

### 4.2 Comportement en Temps Réel
```python
BEHAVIORAL_ANALYSIS = {
    # Monitorer l'activité
    "file_access": True,         # Accès fichiers suspects
    "registry_access": True,     # Accès registry
    "network_access": True,      # Connexions réseau
    "process_creation": True,    # Création de processus
    "dll_loading": True,         # Chargement de DLL
    "memory_allocation": True,   # Allocations mémoire
}
```

---

## PHASE 5 : Scoring Avancé

### 5.1 Système de Corrélation
```python
CORRELATION_RULES = {
    # Règles de corrélation
    "rules": [
        {
            "name": "Cheat Complet",
            "conditions": ["process_suspicious", "file_suspicious", "defender_trace"],
            "score_add": 50,
            "description": "Process + fichier + trace Defender = preuve forte"
        },
        {
            "name": "Injection DLL",
            "conditions": ["unsigned_dll", "high_entropy", "remote_thread"],
            "score_add": 60,
            "description": "DLL non signée + haute entropie + thread distant"
        },
        {
            "name": "Spoofing HWID",
            "conditions": ["hwid_mismatch", "spoof_tool_found"],
            "score_add": 70,
            "description": "HWID ne correspond pas + outil de spoof trouvé"
        }
    ]
}
```

### 5.2 Rapport Détaillé
```json
{
  "verdict": "CHEATER",
  "confidence": 94,
  "evidence": {
    "strong": [
      "Known cheat hash match (ntoskrnl.exe)",
      "Dangerous API imports (VirtualAllocEx, WriteProcessMemory)",
      "VMProtect packer detected",
      "Defender threat trace (file deleted)"
    ],
    "supporting": [
      "High entropy section (.vmp0)",
      "Suspicious folder (Documents\\cheat\\)",
      "USB device disconnected"
    ],
    "false_positive_checks": [
      "Microsoft signature: NOT present",
      "Known legitimate software: NO",
      "Game asset: NO"
    ]
  },
  "risk_breakdown": {
    "binary_analysis": 85,
    "forensic_traces": 70,
    "behavioral": 0,
    "network": 0
  }
}
```

---

## TECHNOLOGIES UTILISÉES

| Technologie | Usage | Priorité |
|---|---|---|
| `pefile` | Analyse PE (imports, sections, ressources) | HAUTE |
| `struct` | Lecture binaire bas-niveau | HAUTE |
| `hashlib` | Hash de fichiers (MD5, SHA256) | HAUTE |
| `subprocess` | Commandes PowerShell/WMI | HAUTE |
| `winreg` | Lecture du registre Windows | HAUTE |
| `psutil` | Scan des processus | HAUTE |
| `ctypes` | Appels Windows API directs | MOYENNE |
| `yara` | Pattern matching binaire avancé | MOYENNE |
| `capstone` | Désassemblage x86/x64 | BASSE |
| `scikit-learn` | Machine Learning | BASSE |

---

## ORDRE D'IMPLÉMENTATION

1. **Semaine 1** : Scan binaire PE (imports + sections + packers)
2. **Semaine 2** : Strings binaire profond + hash amélioré
3. **Semaine 3** : Intégration dans le scan de fichiers existant
4. **Semaine 4** : Scoring avancé + corrélation
5. **Plus tard** : ML + comportemental + désassemblage
