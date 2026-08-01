from pathlib import Path
from PyInstaller.utils.archive import ZlibArchiveReader

exe = Path('dist') / 'anti-scan.exe'
print('exists', exe.exists())
with ZlibArchiveReader(str(exe)) as r:
    names = r.getnames()
print('member count', len(names))
matches = [n for n in names if 'python311.dll' in n.lower()]
print('python311 count', len(matches))
for m in matches[:20]:
    print(m)
