import urllib.request, json, ssl

SUPABASE_URL = 'https://azvlbugdewwjwizksmaq.supabase.co'
SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImF6dmxidWdkZXd3andpemtzbWFxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODU0MTIzNTgsImV4cCI6MjEwMDk4ODM1OH0.mYEwacqQzwKC2wv0M74C6kuSD9y8J5O4H54wNlGwk08'

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# Test 1: Peut-on lire la table 'scans' sans auth ?
print('=== TEST 1: Lecture scans sans auth ===')
url = SUPABASE_URL + '/rest/v1/scans?select=scan_id,hwid&order=timestamp.desc&limit=5'
req = urllib.request.Request(url, headers={
    'apikey': SUPABASE_ANON_KEY,
})
try:
    with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
        data = json.loads(resp.read())
        print('OK - Scans lus:', len(data))
except Exception as e:
    print('ERREUR:', e)

# Test 2: Peut-on ecrire (INSERT) dans 'scans' avec anon key ?
print('\n=== TEST 2: INSERT dans scans avec anon key ===')
test_payload = {
    'scan_id': 'SCAN-TEST-RLS',
    'hwid': 'HWID-TEST-RLS',
    'timestamp': '2026-01-01 00:00:00',
    'system_info': {'test': True},
    'disk_performance': {},
    'stats': {},
    'risk_summary': {'overall_risk_score': 0, 'verdict': 'CLEAN'},
    'applications': []
}
data_bytes = json.dumps(test_payload).encode('utf-8')
req2 = urllib.request.Request(
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
try:
    with urllib.request.urlopen(req2, context=ctx, timeout=10) as resp:
        print('INSERT OK - Status:', resp.status)
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print('INSERT FAILED - HTTP', e.code, ':', body)
except Exception as e:
    print('INSERT ERROR:', e)

# Test 3: PATCH/UPDATE existant scan
print('\n=== TEST 3: UPDATE scan existant ===')
req3 = urllib.request.Request(
    SUPABASE_URL + '/rest/v1/scans?scan_id=eq.SCAN-TEST-RLS',
    data=json.dumps({'hwid': 'HWID-TEST-RLS-UPDATED'}).encode('utf-8'),
    headers={
        'Content-Type': 'application/json',
        'apikey': SUPABASE_ANON_KEY,
        'Authorization': 'Bearer ' + SUPABASE_ANON_KEY,
    },
    method='PATCH'
)
try:
    with urllib.request.urlopen(req3, context=ctx, timeout=10) as resp:
        print('UPDATE OK - Status:', resp.status)
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print('UPDATE FAILED - HTTP', e.code, ':', body)
except Exception as e:
    print('UPDATE ERROR:', e)

# Test 4: Verifier si le scan TEST est apparu
print('\n=== TEST 4: Verifier scan TEST dans la table ===')
url4 = SUPABASE_URL + "/rest/v1/scans?scan_id=eq.SCAN-TEST-RLS&select=scan_id,hwid"
req4 = urllib.request.Request(url4, headers={
    'apikey': SUPABASE_ANON_KEY,
    'Authorization': 'Bearer ' + SUPABASE_ANON_KEY
})
try:
    with urllib.request.urlopen(req4, context=ctx, timeout=10) as resp:
        data4 = json.loads(resp.read())
        if data4:
            print('TEST scan PRESENT dans Supabase:', data4)
        else:
            print('TEST scan ABSENT - RLS bloque probablement INSERT !')
except Exception as e:
    print('ERREUR:', e)
