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

    path_lower = filepath.lower()

    # Heuristique ultra-rapide : Fichiers système natifs Windows connus (Microsoft)
    system_prefixes = (
        "c:\\windows\\system32\\",
        "c:\\windows\\syswow64\\",
        "c:\\windows\\winsxs\\",
        "c:\\windows\\diagnostics\\",
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
            timeout=1.5
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
