import ctypes
from ctypes import wintypes
import hashlib
import os
import threading

_sig_cache = {}
_cache_lock = threading.Lock()

class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_byte * 8),
    ]

WINTRUST_ACTION_GENERIC_VERIFY_V2 = GUID(
    0x00AAC56B, 0xCD44, 0x11D0, (ctypes.c_byte * 8)(0x8C, 0xC2, 0x00, 0xC0, 0x4F, 0xC2, 0x95, 0xEE)
)

class WINTRUST_FILE_INFO(ctypes.Structure):
    _fields_ = [
        ("cbStruct", wintypes.DWORD),
        ("pcwszFilePath", wintypes.LPCWSTR),
        ("hFile", wintypes.HANDLE),
        ("pgKnownSubject", ctypes.c_void_p),
    ]

class WINTRUST_DATA(ctypes.Structure):
    _fields_ = [
        ("cbStruct", wintypes.DWORD),
        ("pPolicyCallbackData", ctypes.c_void_p),
        ("pSIPClientData", ctypes.c_void_p),
        ("dwUIChoice", wintypes.DWORD),
        ("fdwRevocationChecks", wintypes.DWORD),
        ("dwUnionChoice", wintypes.DWORD),
        ("pFile", ctypes.POINTER(WINTRUST_FILE_INFO)),
        ("dwStateAction", wintypes.DWORD),
        ("hWVTStateData", wintypes.HANDLE),
        ("pwszURL", wintypes.LPCWSTR),
        ("dwProvFlags", wintypes.DWORD),
        ("dwUIContext", wintypes.DWORD),
        ("pSignatureSettings", ctypes.c_void_p),
    ]

# WinTrust API setup
try:
    wintrust = ctypes.windll.wintrust
    wintrust.WinVerifyTrust.restype = wintypes.LONG
    wintrust.WinVerifyTrust.argtypes = [wintypes.HWND, ctypes.c_void_p, ctypes.c_void_p]
except Exception:
    wintrust = None

# Crypt32 API setup
try:
    crypt32 = ctypes.windll.crypt32
    crypt32.CryptQueryObject.restype = wintypes.BOOL
    crypt32.CertEnumCertificatesInStore.restype = ctypes.c_void_p
    crypt32.CertEnumCertificatesInStore.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
    crypt32.CertGetNameStringW.restype = wintypes.DWORD
    crypt32.CertGetNameStringW.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.LPWSTR, wintypes.DWORD]
    crypt32.CertFreeCertificateContext.restype = wintypes.BOOL
    crypt32.CertFreeCertificateContext.argtypes = [ctypes.c_void_p]
except Exception:
    crypt32 = None

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

TRUSTED_SIGNER_KEYWORDS = (
    "microsoft corporation", "microsoft windows", "nvidia", "advanced micro devices",
    "intel", "micro-star", "msi", "realtek", "logitech", "razer", "corsair",
    "oracle", "valve", "discord", "google", "mozilla", "epic games", "rockstar",
    "blizzard", "ubisoft", "ea ", "electronic arts", "asustek", "gigabyte",
    "malwarebytes", "brave", "ollama", "python software foundation", "jetbrains",
    "adobe", "unity technologies", "unreal", "battleye", "easy anti-cheat"
)

def is_trusted_signer(signer_str):
    if not signer_str:
        return False
    signer_lower = signer_str.lower()
    return any(kw in signer_lower for kw in TRUSTED_SIGNER_KEYWORDS)

def is_trusted_system_or_signed(filepath):
    """
    Vérifie si le fichier est un composant système Windows officiel
    ou possède une signature valide d'un éditeur de confiance reconnu.
    Ne fait JAMAIS confiance aux dossiers utilisateurs temporaires/téléchargements (Desktop, Downloads, Temp, etc.).
    """
    if not filepath or not os.path.exists(filepath):
        return False
    path_lower = filepath.lower()

    # Ne JAMAIS considérer comme "de confiance" un fichier situé dans des zones de cheats typiques
    high_risk_dirs = (
        "\\downloads\\", "\\desktop\\", "\\temp\\", "\\appdata\\local\\temp\\",
        "\\users\\public\\", "\\documents\\", "\\onedrive\\"
    )
    if any(hrd in path_lower for hrd in high_risk_dirs):
        return False

    # Fichiers situés dans System32 / SysWOW64 Windows natif
    system_prefixes = (
        "c:\\windows\\system32\\",
        "c:\\windows\\syswow64\\",
        "c:\\windows\\winsxs\\",
        "c:\\windows\\diagnostics\\",
        "c:\\windows\\servicing\\",
    )
    if any(path_lower.startswith(p) for p in system_prefixes):
        return True

    # Vérification signature Authenticode : seul un éditeur RECONNU dans Program Files est de confiance
    sig = check_authenticode_signature(filepath)
    if sig.get("signed"):
        signer = sig.get("signer")
        program_prefixes = ("c:\\program files\\", "c:\\program files (x86)\\")
        if any(path_lower.startswith(pp) for pp in program_prefixes) and is_trusted_signer(signer):
            return True

    return False

def _get_native_signer_name(filepath):
    if not crypt32:
        return None
    encoding = wintypes.DWORD()
    contentType = wintypes.DWORD()
    formatType = wintypes.DWORD()
    hStore = wintypes.HANDLE()
    hMsg = wintypes.HANDLE()

    res = crypt32.CryptQueryObject(
        1, # CERT_QUERY_OBJECT_FILE
        ctypes.c_wchar_p(filepath),
        1 << 10, # CERT_QUERY_CONTENT_FLAG_PKCS7_SIGNED_EMBEDDED
        1 << 1,  # CERT_QUERY_FORMAT_FLAG_BINARY
        0,
        ctypes.byref(encoding),
        ctypes.byref(contentType),
        ctypes.byref(formatType),
        ctypes.byref(hStore),
        ctypes.byref(hMsg),
        None
    )
    if not res:
        return None

    signer_name = None
    try:
        pCertContext = crypt32.CertEnumCertificatesInStore(hStore, None)
        if pCertContext:
            cbSize = crypt32.CertGetNameStringW(pCertContext, 4, 0, None, None, 0)
            if cbSize > 1:
                name_buf = ctypes.create_unicode_buffer(cbSize)
                crypt32.CertGetNameStringW(pCertContext, 4, 0, None, name_buf, cbSize)
                signer_name = name_buf.value
            crypt32.CertFreeCertificateContext(pCertContext)
    except Exception:
        pass
    finally:
        if hStore: crypt32.CertCloseStore(hStore, 0)
        if hMsg: crypt32.CryptMsgClose(hMsg)

    return signer_name

def check_authenticode_signature(filepath):
    """
    Vérification ultra-rapide 100% native de la signature numérique Windows avec mise en cache.
    Ne lance AUCUN sous-processus (PowerShell, cmd), 100% sûr contre les crashs et fuites de handles.
    """
    if not filepath or not os.path.exists(filepath):
        return {"status": "FileNotFound", "signed": False, "signer": None}
    
    with _cache_lock:
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
        with _cache_lock:
            _sig_cache[filepath] = res
        return res

    # Signature native WinVerifyTrust (wintrust.dll)
    try:
        if wintrust:
            fi = WINTRUST_FILE_INFO(ctypes.sizeof(WINTRUST_FILE_INFO), filepath, None, None)
            wd = WINTRUST_DATA(
                cbStruct=ctypes.sizeof(WINTRUST_DATA),
                pPolicyCallbackData=None,
                pSIPClientData=None,
                dwUIChoice=2, # WTD_UI_NONE
                fdwRevocationChecks=0, # WTD_REVOKE_NONE
                dwUnionChoice=1, # WTD_CHOICE_FILE
                pFile=ctypes.pointer(fi),
                dwStateAction=0,
                hWVTStateData=None,
                pwszURL=None,
                dwProvFlags=0x00000080, # WTD_REVOCATION_CHECK_NONE
                dwUIContext=0,
                pSignatureSettings=None
            )
            lStatus = wintrust.WinVerifyTrust(None, ctypes.byref(WINTRUST_ACTION_GENERIC_VERIFY_V2), ctypes.byref(wd))
            is_valid = (lStatus == 0)
            signer_name = _get_native_signer_name(filepath) if is_valid else None
            res = {
                "status": "Valid" if is_valid else "Unsigned",
                "signed": is_valid,
                "signer": signer_name or ("Signed Executable" if is_valid else None)
            }
        else:
            res = {"status": "Unknown", "signed": False, "signer": None}
    except Exception:
        res = {"status": "Unknown", "signed": False, "signer": None}

    with _cache_lock:
        _sig_cache[filepath] = res
    return res
