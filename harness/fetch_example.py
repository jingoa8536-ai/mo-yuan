import urllib.request
import sys

req = urllib.request.Request('https://example.com', headers={'User-Agent': 'Mozilla/5.0'})
try:
    resp = urllib.request.urlopen(req, timeout=15)
    sys.stdout.write('Status: ' + str(resp.status) + '\n')
    html = resp.read().decode('utf-8')
    sys.stdout.write('Length: ' + str(len(html)) + '\n')
    sys.stdout.write('---HTML START---\n')
    sys.stdout.write(html)
    sys.stdout.write('\n---HTML END---\n')
except Exception as e:
    sys.stdout.write('Error: ' + str(e) + '\n')
