# 🛡️ ANTI Defense System — Architecture v1.9

## Vue d'ensemble

ANTI est un scanner forensique anti-cheat distribué composé de trois couches :

1. **EXE Client** — Exécutable lancé sur la machine du joueur
2. **Supabase** — Base de données cloud centralisée (réception des scans)
3. **Dashboard Web** — Interface React pour les admins (lecture des résultats)

---

## 🗂️ Structure du projet

```
ANTI/
├── main.py                  ← Point d'entrée de l'application
├── version.json             ← Numéro de version (vérifié au démarrage)
├── install.ps1              ← Script PowerShell de déploiement joueur
├── requirements.txt         ← Dépendances Python (psutil)
├── ANTI.spec                ← Spec PyInstaller (build du .exe)
│
├── src/
│   ├── scanner.py           ← Moteur de scan forensique (8 sources)
│   ├── scorer.py            ← Calcul du score de risque & verdict
│   ├── admin_sync.py        ← Envoi JSON vers Supabase (REST API)
│   ├── ui.py                ← Affichage terminal (banner + progress)
│   ├── authenticode.py      ← Vérification signatures numériques
│   └── storage.py           ← Cache local (lecture config.json)
│
├── dist/
│   └── ANTI.exe             ← Binaire compilé (PyInstaller) — à distribuer
│
└── web/
    ├── src/
    │   ├── App.jsx                       ← Routing + authentification
    │   ├── main.jsx                      ← Point d'entrée React
    │   ├── index.css                     ← Design system global
    │   ├── lib/
    │   │   └── supabase.js               ← Client Supabase JS
    │   └── components/
    │       ├── LoginPage.jsx             ← Authentification admin
    │       ├── Header.jsx                ← Navigation principale
    │       ├── ScanTable.jsx             ← Tableau des scans reçus
    │       ├── StatsRow.jsx              ← Compteurs globaux
    │       ├── MachineDetailPage.jsx     ← Vue détaillée d'un joueur
    │       ├── DetailModal.jsx           ← Modal scan + Copy JSON
    │       └── AdminManager.jsx          ← Gestion des comptes admin
    └── package.json
```

---

## 🔄 Séquence d'exécution complète

```
┌─────────────────────────────────────────────────────────┐
│                  MACHINE DU JOUEUR                       │
│                                                         │
│  1. install.ps1                                         │
│     └─ Télécharge ANTI.exe depuis GitHub                │
│     └─ Lance ANTI.exe en mode Administrateur            │
│                                                         │
│  2. main.py (orchestrateur)                             │
│     ├─ get_next_scan_id_from_supabase()                 │
│     │    └─ Récupère le prochain SCAN-XXXXX             │
│     │                                                   │
│     ├─ run_system_scan() [scanner.py]                   │
│     │    ├─ Processus actifs & DLLs injectées           │
│     │    ├─ Dossiers suspects (FiveM, AppData...)        │
│     │    ├─ Archives ZIP/RAR suspectes                   │
│     │    ├─ Fichiers Récents (.lnk shortcuts)            │
│     │    ├─ Corbeille ($RECYCLE.BIN)                    │
│     │    ├─ Prefetch Windows (*.pf)                     │
│     │    │    └─ Détecte volumes USB d'origine          │
│     │    ├─ USN Journal NTFS (fichiers supprimés)        │
│     │    ├─ Windows Defender (historique menaces)        │
│     │    ├─ Historique USB (registre USBSTOR)           │
│     │    └─ Infos système (CPU, RAM, GPU, HWID...)      │
│     │                                                   │
│     ├─ calculate_overall_risk_grouped() [scorer.py]     │
│     │    ├─ Score de risque par application             │
│     │    └─ Verdict global : CLEAN / ANORMAL / CHEATER  │
│     │                                                   │
│     ├─ transmit_scan_to_supabase() [admin_sync.py]      │
│     │    └─ HTTPS POST JSON → Supabase REST API         │
│     │                                                   │
│     └─ print_client_completion() [ui.py]                │
│          └─ Affiche SCAN-XXXXX anonymisé dans terminal  │
└─────────────────────────────────────────────────────────┘
                          │
                          │  JSON complet (HTTPS)
                          ▼
┌─────────────────────────────────────────────────────────┐
│              SUPABASE (Base de données cloud)           │
│                                                         │
│  Table : scans                                          │
│  ┌──────────┬──────────┬───────────┬──────────────────┐ │
│  │ scan_id  │   hwid   │ timestamp │  system_info     │ │
│  │ SCAN-XXX │ HWID-... │ 2026-...  │  { cpu, ram... } │ │
│  ├──────────┴──────────┴───────────┴──────────────────┤ │
│  │ applications[] | risk_summary | stats | ...        │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
                          │
                          │  Supabase JS (lecture temps réel)
                          ▼
┌─────────────────────────────────────────────────────────┐
│              DASHBOARD WEB ADMIN (React + Vite)         │
│                                                         │
│  LoginPage → [admin authentifié]                        │
│       │                                                 │
│       ├─ ScanTable      → liste tous les scans          │
│       │   └─ filtre : CLEAN / ANORMAL / CHEATER         │
│       │                                                 │
│       ├─ MachineDetailPage → détail d'un joueur         │
│       │   ├─ Score de risque global                     │
│       │   ├─ Applications suspectes avec risk badge     │
│       │   ├─ Traces Prefetch / USN / Defender           │
│       │   ├─ Historique USB                             │
│       │   ├─ Copie de chemin en 1 clic                  │
│       │   └─ "Copier JSON du Scan" → presse-papier      │
│       │                                                 │
│       └─ AdminManager   → gestion des comptes admin     │
└─────────────────────────────────────────────────────────┘
```

---

### Critères de scoring par application

| Condition | Score ajouté |
|-----------|-------------|
| Usurpation de nom système (ex: `svchost.exe` hors `C:\Windows`) | +70 |
| Exécutable non signé dans `%TEMP%` ou `Public` | +45 |
| Composant système sans signature valide | +50 |
| Exécutable signé dans `%TEMP%` | +15 |
| Binaire non signé dans AppData utilisateur | +5 |

### Modificateurs globaux

| Condition | Effet |
|-----------|-------|
| Formatage récent < 48h | Score forcé ≥ 35, confiance FAIBLE |
| Prefetch purgé (< 15 fichiers .pf) | Score forcé ≥ 65, confiance SUSPECTE |
| USB/SSD débranché récemment | Information forensique uniquement (pas de sur-scoring) |

---

## 📡 Sources de données forensiques (scanner.py)

| Source | Données récupérées |
|--------|-------------------|
| **Processus actifs** | EXE en cours, DLLs injectées, PID, chemin |
| **Dossiers suspects** | FiveM plugins/, AppData, Bureau, Downloads |
| **Archives ZIP/RAR** | Contenu d'archives pour cheats emballés |
| **Fichiers Récents** | `.lnk` dans `Recent\` → cible d'origine (ex: `E:\loader.exe`) |
| **Corbeille** | `$RECYCLE.BIN` — fichiers non vidés suspects |
| **Prefetch Windows** | `C:\Windows\Prefetch\*.pf` — nom exe + dernière exécution + volume USB source |
| **USN Journal NTFS** | Fichiers supprimés récents sur chaque partition NTFS |
| **Windows Defender** | Historique des menaces détectées (Get-MpThreatDetection) |
| **Historique USB** | Registre `HKLM\SYSTEM\...\USBSTOR` — tous les périphériques connectés |
| **Infos système** | HWID, CPU, RAM, GPU, OS, IP locale, disques montés |

---

## 🧲 Détection d'exécution depuis disque externe

Même si une clé USB est **débranchée**, Windows conserve des preuves indélébiles :

1. **Prefetch** — Un fichier `.pf` est créé pour chaque `.exe` lancé, y compris depuis `D:\`, `E:\`, etc. Le scanner lit les métadonnées binaires brutes pour extraire l'identifiant du volume d'origine (`\HARDDISKVOLUME...`).

2. **Fichiers Récents** — Les raccourcis `.lnk` pointent vers la cible d'origine, même si le disque est absent.

3. **USN Journal** — Si des fichiers ont été copiés depuis la clé USB puis supprimés, le journal NTFS garde les traces.

---

## 🚀 Commandes de build & push

```powershell
# Recompiler l'exécutable
pyinstaller --onefile --name ANTI main.py --distpath dist

# Forcer le push de tout (sources + exe)
git add -f dist/ANTI.exe
git add main.py src/ui.py src/scanner.py src/scorer.py version.json
git commit -m "vX.X: description des changements"
git push --force origin main
```

---

## 📦 Flux de distribution

```
GitHub (AdamZoda/ANTI)
    └─ dist/ANTI.exe           ← binaire public
    └─ install.ps1             ← script de déploiement

Serveur Vercel (website-anti)
    └─ /install                ← sert install.ps1 dynamiquement

Joueur exécute :
    iex (iwr "https://website-anti.vercel.app/install").Content
```
