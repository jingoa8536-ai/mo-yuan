import urllib.request
import xml.etree.ElementTree as ET
import json

url = 'https://export.arxiv.org/api/query?search_query=cat:cs.AI&sortBy=submittedDate&sortOrder=descending&max_results=15'
data = urllib.request.urlopen(url, timeout=30).read().decode('utf-8')
root = ET.fromstring(data)

ns = {'atom': 'http://www.w3.org/2005/Atom'}

results = []
for i, entry in enumerate(root.findall('atom:entry', ns), 1):
    title = entry.find('atom:title', ns).text.strip().replace('\n', ' ').replace('  ', ' ')
    published = entry.find('atom:published', ns).text[:10]
    authors_el = entry.findall('atom:author', ns)
    authors = ', '.join([a.find('atom:name', ns).text for a in authors_el[:4]])
    if len(authors_el) > 4:
        authors += ' et al.'
    summary = entry.find('atom:summary', ns).text.strip().replace('\n', ' ').replace('  ', ' ')[:300]
    link = entry.find('atom:id', ns).text
    
    results.append({
        'id': i,
        'title': title,
        'published': published,
        'authors': authors,
        'summary': summary,
        'link': link
    })

# Save as JSON as well (bonus for the user's request)
with open('arxiv_results.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

# Print all results
for r in results:
    print(f"===== #{r['id']:2d} ===== [{r['published']}]")
    print(f"📄 {r['title']}")
    print(f"👤 {r['authors']}")
    print(f"📝 {r['summary']}...")
    print(f"🔗 {r['link']}")
    print()
