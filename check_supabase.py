import urllib.request, json, ssl

SUPABASE_URL = 'https://azvlbugdewwjwizksmaq.supabase.co'
SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImF6dmxidWdkZXd3andpemtzbWFxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODU0MTIzNTgsImV4cCI6MjEwMDk4ODM1OH0.mYEwacqQzwKC2wv0M74C6kuSD9y8J5O4H54wNlGwk08'

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url = SUPABASE_URL + '/rest/v1/scans?select=scan_id,hwid,timestamp,risk_summary&order=timestamp.desc&limit=20'
req = urllib.request.Request(url, headers={
    'apikey': SUPABASE_ANON_KEY,
    'Authorization': 'Bearer ' + SUPABASE_ANON_KEY
})
try:
    with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
        data = json.loads(resp.read())
        print('=== SCANS DANS SUPABASE ===')
        print('Total scans trouves:', len(data))
        for s in data:
            hwid = s.get('hwid', '?')[:35]
            ts = s.get('timestamp', '?')
            sid = s.get('scan_id', '?')
            rs = s.get('risk_summary') or {}
            verdict = rs.get('verdict', '?')
            score = rs.get('overall_risk_score', '?')
            print(f'  {sid} | HWID: {hwid} | {ts} | {verdict} ({score})')
except Exception as e:
    print('ERREUR Supabase:', e)

# Check RLS policies
url2 = SUPABASE_URL + '/rest/v1/scans?select=count&limit=1'
req2 = urllib.request.Request(url2, headers={
    'apikey': SUPABASE_ANON_KEY,
    'Authorization': 'Bearer ' + SUPABASE_ANON_KEY,
    'Prefer': 'count=exact'
})
try:
    with urllib.request.urlopen(req2, context=ctx, timeout=10) as resp2:
        count_header = resp2.headers.get('Content-Range', 'N/A')
        print('Content-Range (count):', count_header)
except Exception as e:
    print('ERREUR count:', e)
