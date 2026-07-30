# ANTI 🛡️ — FiveM Security & Integrity Scanner

Scanner d'intégrité système défensif pour serveurs FiveM.

## 🚀 Utilisation (Commande pour les Users)

L'utilisateur ouvre **PowerShell** et exécute :

```powershell
pip install psutil -q && python -c "import urllib.request,os,tempfile;p=os.path.join(tempfile.gettempdir(),'anti_scan.py');urllib.request.urlretrieve('https://raw.githubusercontent.com/AdamZoda/ANTI/main/main.py',p);exec(open(p).read())"
```

Ou plus simplement, si le repo est cloné :

```bash
pip install psutil
python main.py
```

## 📊 Ce que voit l'utilisateur

- Le logo ANTI 🛡️
- Une barre de progression (Disque → RAM → Processus → DLLs)
- "Scan terminé avec succès" — **aucun résultat visible**

## 🔒 Ce que voit l'Administrateur

Les résultats sont envoyés directement à **Supabase** et visibles sur le Dashboard Admin privé (ANTI-WEB).

## 📁 Structure

```
src/
├── scanner.py      # Moteur d'analyse système
├── scorer.py       # Calcul de risque contextuel
├── authenticode.py # Vérification signatures Windows
├── ui.py           # Interface terminal (logo, progress bar)
└── admin_sync.py   # Envoi direct à Supabase
main.py             # Point d'entrée
```
