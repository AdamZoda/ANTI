import os

filepath = r"c:\Users\adamm\Documents\ANTI\src\scanner.py"
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

target = """                dirs[:] = [
                    d for d in dirs
                    if d.lower() not in {
                        "windows", "program files", "program files (x86)",
                        "system32", "syswow64", "ea", "playnite", "razor",
                        "system volume information", "programdata", "programdata",
                        "recovery", "perflogs", "winsxs", "servicing",
                        "node_modules", ".git", ".cache", "gpu_cache",
                        "microsoft", "windows", "nvidia", "amd", "intel",
                        "common files", "internet explorer", "windows defender",
                        "windowsapps", "onedrive", "packages", "publisher",
                        "application data", "cookies", "history", "temporary internet files"
                    } and not d.lower().startswith(IGNORED_DIR_PREFIXES)
                ]"""

replacement = """                dirs[:] = [
                    d for d in dirs
                    if d.lower() not in {
                        "windows", "program files", "program files (x86)",
                        "system32", "syswow64", "ea", "playnite", "razor",
                        "system volume information", "programdata", "recovery", 
                        "perflogs", "winsxs", "servicing", "node_modules", 
                        ".git", ".cache", "gpu_cache", "microsoft", "nvidia", 
                        "amd", "intel", "common files", "internet explorer", 
                        "windows defender", "windowsapps", "onedrive", "packages", 
                        "publisher", "application data", "cookies", "history", 
                        "temporary internet files", "steam", "steamlibrary", 
                        "epic games", "riot games", "ubisoft", "origin", 
                        "origin games", "rockstar games", "gta v", "gtav", 
                        "social club", "battlenet", "battle.net", "geforce experience"
                    ] and not d.lower().startswith(IGNORED_DIR_PREFIXES)
                ]"""

# Try replacing with exact matches of both CRLF and LF
if target in content:
    content = content.replace(target, replacement)
    print("Replaced with LF format successfully")
else:
    target_crlf = target.replace("\n", "\r\n")
    replacement_crlf = replacement.replace("\n", "\r\n")
    if target_crlf in content:
        content = content.replace(target_crlf, replacement_crlf)
        print("Replaced with CRLF format successfully")
    else:
        # Try doing substring logic
        print("Target block not found directly, trying lenient replace")
        # Find where programdata is defined twice
        pdata_double = '"system volume information", "programdata", "programdata",'
        pdata_single = '"system volume information", "programdata", "recovery",'
        if pdata_double in content:
            content = content.replace(pdata_double, pdata_single)
            # Remove "recovery" from next lines to keep list clean
            content = content.replace('"recovery", "perflogs"', '"perflogs"')
            # Append other folders before "temporary internet files"
            find_last_folders = '"publisher", "application data", "cookies", "history", "temporary internet files"'
            replace_last_folders = '"publisher", "application data", "cookies", "history", "temporary internet files", "steam", "steamlibrary", "epic games", "riot games", "ubisoft", "origin", "origin games", "rockstar games", "gta v", "gtav", "social club", "battlenet", "battle.net", "geforce experience"'
            if find_last_folders in content:
                content = content.replace(find_last_folders, replace_last_folders)
                print("Lenient replace succeeded!")
            else:
                find_last_folders_crlf = find_last_folders.replace("\n", "\r\n")
                replace_last_folders_crlf = replace_last_folders.replace("\n", "\r\n")
                if find_last_folders_crlf in content:
                    content = content.replace(find_last_folders_crlf, replace_last_folders_crlf)
                    print("Lenient CRLF replace succeeded!")
                else:
                    print("Lenient replace failed to find targets")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
