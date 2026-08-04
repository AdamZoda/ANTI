# ANTI — Architecture

## Vue d'ensemble

ANTI est un scanner forensique anti-cheat pour serveurs FiveM. Il analyse les machines des joueurs et envoie les résultats à un dashboard admin via Supabase.

## Composants

```
EXE Client (Python)  ──HTTPS──>  Supabase (DB cloud)  ──>  Dashboard Web (React)
```

| Composant | Rôle |
|-----------|------|
| `main.py` | Orchestrateur — gère le cycle de vie du scan |
| `src/scanner.py` | Moteur d'analyse forensique (processus, DLL, Prefetch, USN, USB, Amcache, VM/RDP) |
| `src/scorer.py` | Calcul du score de risque et verdict (CLEAN / ANORMAL / CHEATER) |
| `src/authenticode.py` | Vérification des signatures numériques Windows |
| `src/admin_sync.py` | Communication Supabase (REST API) + notifications Discord |
| `src/ui.py` | Interface terminal (banner, barre de progression) |
| `src/storage.py` | Cache local (config.json) |
| `server/` | Backend Node.js (API webhook) |
| `web/` | Dashboard admin React (Vite + Supabase JS) |

## Données scannées

| Source | Ce qu'on récupère |
|--------|-------------------|
| Processus actifs | EXE, DLL injectées, PID, chemin |
| Dossiers suspects | FiveM plugins/, AppData, Bureau, Downloads |
| Archives ZIP/RAR | Contenu d'archives (cheats emballés) |
| Fichiers Récents | Raccourcis `.lnk` → cible d'origine |
| Corbeille | `$RECYCLE.BIN` — fichiers non vidés |
| Prefetch Windows | `*.pf` — traces d'exécution + volume USB source |
| USN Journal NTFS | Fichiers supprimés récents |
| Windows Defender | Historique des menaces |
| Historique USB | Registre USBSTOR — périphériques connectés |
| Amcache.hve | SHA1 + chemin de tous les exécutables jamais lancés |
| BAM/UserAssist | Registre — exécutables lancés via Explorer |
| Connexions réseau | Ports suspects (1337, 4444, etc.) |
| VM/Sandbox/RDP | Détection d'environnement virtuel |
| Infos système | HWID, CPU, RAM, GPU, OS, IP, disques |

## Score de risque

| Condition | Score |
|-----------|-------|
| Usurpation de nom système (`svchost.exe` hors `C:\Windows`) | +70 |
| Exécutable non signé dans `%TEMP%` ou `Public` | +45 |
| Composant système sans signature valide | +50 |
| Exécutable signé dans `%TEMP%` | +15 |
| Binaire non signé dans AppData | +5 |
| Prefetch purgé (< 15 .pf) | Score forcé ≥ 65 |
| Formatage récent < 48h | Score forcé ≥ 35 |

**Verdict :** CLEAN (< 30) / ANORMAL (30-59) / CHEATER (≥ 60)

## Flux d'exécution

```
1. Vérification mise à jour silencieuse
2. Watchdog (timeout 3 min)
3. Nettoyage pré-scan
4. Banner terminal
5. Récupération HWID
6. Validation code PIN (OTP 5-6 caractères)
7. Récupération scan_id depuis Supabase
8. Envoi initial (SCANNING_IN_PROGRESS)
9. Scan système complet
10. Calcul score de risque
11. Transmission Supabase
12. Notification Discord
13. Auto-destruction de l'EXE
```

## Génération de l'EXE

### Prérequis

```powershell
pip install pyinstaller psutil requests
```

### Commande de build

```powershell
pyinstaller --onefile --name ANTI main.py --distpath dist
```

### Options utiles

| Option | Effet |
|--------|-------|
| `--onefile` | Génère un seul fichier EXE |
| `--name ANTI` | Nom du fichier de sortie |
| `--distpath dist` | Dossier de sortie |
| `--icon=icon.ico` | Icône personnalisée |
| `--add-data "config.json;."` | Inclure config.json dans l'EXE |
| `--noconsole` | Pas de fenêtre console (GUI) |

### Exemple complet avec assets

```powershell
pyinstaller --onefile --name ANTI --distpath dist --add-data "config.json;." main.py
```

### Push vers GitHub

```powershell
git add -f dist/ANTI.exe
git add main.py src/*.py version.json requirements.txt ANTI.spec install.ps1
git commit -m "vX.X: description"
git push origin main
```
