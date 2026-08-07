import hashlib
import os
import subprocess

_sig_cache = {}

def get_file_sha256(filepath):
    """Calcule le hachage SHA-256 d'un fichier rapidement."""
    if not filepath or not os.path.exists(filepath):
        return None
    try:
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return None

def check_authenticode_signature(filepath):
    """
    Vérification ultra-rapide de la signature numérique Windows avec mise en cache.
    """
    if not filepath or not os.path.exists(filepath):
        return {"status": "FileNotFound", "signed": False, "signer": None}
    
    if filepath in _sig_cache:
        return _sig_cache[filepath]

TRUSTED_SIGNER_KEYWORDS = (
    "microsoft corporation", "microsoft windows", "nvidia", "advanced micro devices",
    "intel", "micro-star", "msi", "realtek", "logitech", "razer", "corsair",
    "oracle", "valve", "discord", "google", "mozilla", "epic games", "rockstar",
    "blizzard", "ubisoft", "ea ", "electronic arts", "asustek", "gigabyte"
)

def is_trusted_signer(signer_str):
    if not signer_str:
        return False
    signer_lower = signer_str.lower()
    return any(kw in signer_lower for kw in TRUSTED_SIGNER_KEYWORDS)

def is_trusted_system_or_signed(filepath):
    """
    Vérifie si le fichier est un composant système Windows officiel
    ou possède une signature valide d'un éditeur de confiance.
    """
    if not filepath or not os.path.exists(filepath):
        return False
    path_lower = filepath.lower()
    system_prefixes = (
        "c:\\windows\\system32\\",
        "c:\\windows\\syswow64\\",
        "c:\\windows\\winsxs\\",
        "c:\\windows\\diagnostics\\",
        "c:\\windows\\servicing\\",
    )
    if any(path_lower.startswith(p) for p in system_prefixes):
        return True
    
    sig = check_authenticode_signature(filepath)
    if sig.get("signed"):
        signer = sig.get("signer")
        if not signer or is_trusted_signer(signer):
            return True
    return False

def check_authenticode_signature(filepath):
    """
    Vérification ultra-rapide de la signature numérique Windows avec mise en cache.
    """
    if not filepath or not os.path.exists(filepath):
        return {"status": "FileNotFound", "signed": False, "signer": None}
    
    if filepath in _sig_cache:
        return _sig_cache[filepath]

    path_lower = filepath.lower()

    # Heuristique ultra-rapide : Fichiers système natifs Windows connus (Microsoft)
    system_prefixes = (
        "c:\\windows\\system32\\",
        "c:\\windows\\syswow64\\",
        "c:\\windows\\winsxs\\",
        "c:\\windows\\diagnostics\\",
        "c:\\windows\\servicing\\",
    )
    if any(path_lower.startswith(p) for p in system_prefixes):
        res = {"status": "Valid", "signed": True, "signer": "CN=Microsoft Windows, O=Microsoft Corporation"}
        _sig_cache[filepath] = res
        return res

    try:
        ps_cmd = f"$s = Get-AuthenticodeSignature -FilePath '{filepath}'; $s.Status.ToString() + '|' + ($s.SignerCertificate.Subject)"
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=1.5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        output = result.stdout.strip()
        if "|" in output:
            status, signer = output.split("|", 1)
            is_valid = status.lower() == "valid"
            res = {
                "status": status,
                "signed": is_valid,
                "signer": signer.strip() if signer and signer != "null" else None
            }
        else:
            res = {"status": output or "Unknown", "signed": False, "signer": None}
    except Exception:
        res = {"status": "Unknown", "signed": False, "signer": None}

    _sig_cache[filepath] = res
    return res

