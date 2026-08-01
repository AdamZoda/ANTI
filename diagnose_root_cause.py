import urllib.request, json, ssl, time, sys

# Simuler exactement ce que fait l'EXE quand un autre user scanne
SUPABASE_URL = 'https://azvlbugdewwjwizksmaq.supabase.co'
SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImF6dmxidWdkZXd3andpemtzbWFxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODU0MTIzNTgsImV4cCI6MjEwMDk4ODM1OH0.mYEwacqQzwKC2wv0M74C6kuSD9y8J5O4H54wNlGwk08'

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

print('='*60)
print('ANALYSE CAUSE RACINE - Pourquoi les scans users ne s arrivent pas')
print('='*60)

# PROBLEME 1: L'ancien code n'avait PAS de context SSL
print('\n[PROBLEME 1] Test SANS SSL context (ancienne version EXE):')
url = SUPABASE_URL + '/rest/v1/scans?select=scan_id&order=timestamp.desc&limit=1'
req = urllib.request.Request(url, headers={
    'apikey': SUPABASE_ANON_KEY,
    'Authorization': 'Bearer ' + SUPABASE_ANON_KEY
})
try:
    # Sans context SSL - peut echouer sur certains Windows avec certs expires
    with urllib.request.urlopen(req, timeout=5) as resp:
        print('  SANS SSL ctx: OK (machine avec certs valides)')
except Exception as e:
    print('  SANS SSL ctx: ECHEC ->', type(e).__name__, str(e))
    print('  --> C est probablement le prob sur les machines des users !')

print('\n[PROBLEME 2] Test AVEC SSL context (nouvelle version EXE):')
req2 = urllib.request.Request(url, headers={
    'apikey': SUPABASE_ANON_KEY,
    'Authorization': 'Bearer ' + SUPABASE_ANON_KEY
})
try:
    with urllib.request.urlopen(req2, context=ctx, timeout=5) as resp:
        print('  AVEC SSL ctx: OK')
except Exception as e:
    print('  AVEC SSL ctx: ECHEC ->', type(e).__name__, str(e))

# PROBLEME 3: Timeout trop court (12s sur un PC lent)
print('\n[PROBLEME 3] Timeouts analyses:')
print('  Ancien: transmit_scan_to_supabase timeout=12s (scan_data peut etre enorme)')
print('  Nouveau: transmit_scan_to_supabase timeout=15s + fallback requests.post')

# PROBLEME 4: Payload trop grand
print('\n[PROBLEME 4] Test payload lourd (simule scan complet):')
big_payload = {
    'scan_id': 'SCAN-DIAG-001',
    'hwid': 'HWID-DIAG-TEST',
    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
    'system_info': {'test': 'x'*1000},
    'disk_performance': {},
    'stats': {},
    'risk_summary': {'overall_risk_score': 50, 'verdict': 'ANORMAL'},
    'applications': [{'app_name': f'app_{i}', 'exe_path': 'test', 'sha256': None, 
                       'signature': {}, 'instances_count': 1, 'pids': [i],
                       'total_dll_count': 5, 'status_type': 'PROCESSUS',
                       'risk_assessment': {'risk_score': 30, 'observations': []}} 
                     for i in range(200)]
}
data_bytes = json.dumps(big_payload).encode('utf-8')
print(f'  Taille payload test (200 apps): {len(data_bytes)/1024:.1f} KB')

req3 = urllib.request.Request(
    SUPABASE_URL + '/rest/v1/scans',
    data=data_bytes,
    headers={
        'Content-Type': 'application/json',
        'apikey': SUPABASE_ANON_KEY,
        'Authorization': 'Bearer ' + SUPABASE_ANON_KEY,
        'Prefer': 'resolution=merge-duplicates'
    },
    method='POST'
)
t0 = time.time()
try:
    with urllib.request.urlopen(req3, context=ctx, timeout=15) as resp:
        elapsed = time.time() - t0
        print(f'  INSERT gros payload: OK ({elapsed:.2f}s) status={resp.status}')
except Exception as e:
    elapsed = time.time() - t0
    print(f'  INSERT gros payload: ECHEC apres {elapsed:.2f}s ->', e)

# Cleanup
req_del = urllib.request.Request(
    SUPABASE_URL + '/rest/v1/scans?scan_id=eq.SCAN-DIAG-001',
    headers={'apikey': SUPABASE_ANON_KEY, 'Authorization': 'Bearer ' + SUPABASE_ANON_KEY},
    method='DELETE'
)
try:
    with urllib.request.urlopen(req_del, context=ctx, timeout=5) as r:
        pass
except: pass

# PROBLEME 5: Scan ID duplique
print('\n[PROBLEME 5] Race condition scan_id:')
print('  Si 2 users scannent en meme temps -> meme SCAN-XXXXX -> 409 conflit -> retry random')
print('  MAIS dans l ancien code: retry sans SSL = re-echec ! Boucle infinie muette.')

# RESUME
print('\n' + '='*60)
print('RESUME DES CAUSES TROUVEES:')
print('='*60)
print()
print('CAUSE #1 [PROBABLE PRINCIPALE]: SSL Certificate Error')
print('  - L ancien EXE faisait urlopen(req, timeout=12) SANS context SSL')
print('  - Sur les PC des users avec Windows mal configure ou certs expires')
print('  - -> EXCEPTION silencieuse -> os._exit(1) -> aucun scan envoye')
print()
print('CAUSE #2: Timeout trop court (12s)')
print('  - Sur un PC lent avec 300+ apps, le payload JSON peut etre tres lourd')
print('  - 12s insuffisant = timeout = echec silencieux')
print()
print('CAUSE #3: Pas de fallback')
print('  - Si urllib echoue, rien d autre ne prend le relais')
print('  - Le scan est perdu definitivement')
print()
print('CAUSE #4: Pas d envoi initial')
print('  - Si le scanner crashe EN COURS de scan (ex: scanner.py plante)')
print('  - Zero donnee envoyee, la machine n apparait jamais sur le site')
print()
print('FIXES APPLIQUES dans la v3.0:')
print('  ✅ SSL context partout (_get_ssl_context)')
print('  ✅ Timeout 15s + fallback requests.post')
print('  ✅ transmit_initial_scan en debut de scan')
print('  ✅ transmit_crash si le scanner plante')
print('  ✅ Watchdog crash report si timeout 6min')
